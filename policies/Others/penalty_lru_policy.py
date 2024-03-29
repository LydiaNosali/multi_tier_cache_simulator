import math
from collections import OrderedDict

from simpy.core import Environment

from common.packet import Packet
from common.penalty import get_alpha
from forwarder_structures.content_store.tier import Tier
from forwarder_structures.forwarder import Forwarder
from policies.policy import Policy


class PenaltyLRUPolicy(Policy):
    def __init__(self, env: Environment, forwarder: Forwarder, tier: Tier):
        Policy.__init__(self, env, forwarder, tier)
        self.name = "LRUorPriority"
        self.nb_packets_capacity = math.trunc(self.tier.max_size * self.tier.target_occupation / forwarder.slot_size)
        print(self.nb_packets_capacity)
        self.lru_dict = OrderedDict()

    def on_packet_access(self, env: Environment, res, packet: Packet, is_write: bool, cause=None):
        print('%s arriving at %s for %s %s' % (self.tier.name, env.now, is_write, packet.name))

        if self.nb_packets_capacity == 0:
            print("Disk cache units == 0")
            return
        if is_write:
            # if the packet is not already in cache, prepare its insertion
            if packet.name not in self.lru_dict:
                if len(self.lru_dict) >= self.nb_packets_capacity:
                    lru_name, lru_old = self.lru_dict.popitem(last=False)
                    # index update
                    yield env.process(self.forwarder.index.del_packet_from_cs(lru_name))
                    # evict data
                    self.tier.number_of_eviction_from_this_tier += 1
                    self.tier.number_of_packets -= 1
                    self.tier.used_size -= lru_old.size
                    print("evict from disk %s" % lru_old.name)
                # index update
                yield env.process(self.forwarder.index.update_packet_tier(packet.name, self.tier))
                if packet.priority == "h":
                    self.lru_dict[packet.name] = packet
                else:
                    lst = list(self.lru_dict.items())
                    lst.insert(round(self.nb_packets_capacity / get_alpha()), (packet.name, packet))
                    # Convert back to an ordered dictionary
                    self.lru_dict = OrderedDict(lst)
                # increment number of writes
                self.tier.used_size += packet.size
                self.tier.number_of_packets += 1
                self.tier.number_of_write += 1
        elif packet.name in self.lru_dict:
            if packet.priority == "h":
                self.lru_dict[packet.name] = packet
            else:
                lst = list(self.lru_dict.items())
                lst.insert(round(self.nb_packets_capacity / get_alpha()), (packet.name, packet))
                # Convert back to an ordered dictionary
                self.lru_dict = OrderedDict(lst)
        with res[1].request() as req:
            yield req
            print('%s starting at %s for %s %s' % (self.tier.name, env.now, is_write, packet.name))
            if is_write:
                yield env.timeout(self.tier.latency + packet.size / self.tier.write_throughput)
                # update time spent writing
                self.tier.time_spent_writing += self.tier.latency + packet.size / self.tier.write_throughput
            else:
                if packet.name in self.lru_dict:
                    yield env.timeout(self.tier.latency + packet.size / self.tier.read_throughput)
                    # update time spent reading
                    if packet.priority == 'l':
                        self.tier.low_p_data_retrieval_time += env.now - packet.timestamp
                    else:
                        self.tier.high_p_data_retrieval_time += env.now - packet.timestamp
                    self.tier.time_spent_reading += self.tier.latency + packet.size / self.tier.read_throughput
                    # increment number of reads
                    self.tier.number_of_reads += 1
                    yield env.timeout(self.tier.latency + packet.size / self.tier.write_throughput)
                    # update time spent writing
                    self.tier.time_spent_writing += self.tier.latency + packet.size / self.tier.write_throughput
                    # increment number of writes
                    self.tier.number_of_write += 1
            res[1].release(req)
            print('%s leaving the resource at %s for %s %s' % (self.tier.name, env.now, is_write, packet.name))

    def prefetch_packet(self, env: Environment, packet: Packet):
        print("prefetch packet from " + self.tier.name.__str__())
        if packet.name in self.lru_dict:
            # index update
            yield env.process(self.forwarder.index.del_packet_from_cs(packet.name))
            del self.lru_dict[packet.name]
            # evict data
            self.tier.number_of_prefetching_from_this_tier += 1
            self.tier.used_size -= packet.size
            self.tier.number_of_packets -= 1
