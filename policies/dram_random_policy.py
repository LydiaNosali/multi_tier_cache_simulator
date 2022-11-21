import math
import random
from decimal import Decimal
from policies.policy import Policy
from forwarder_structures import Forwarder, Tier, Packet
from simpy.core import Environment


class DRAMRandPolicy(Policy):
    def __init__(self, env: Environment, forwarder: Forwarder, tier: Tier):
        Policy.__init__(self, env, forwarder, tier)
        self.nb_packets_capacity = math.trunc(self.tier.max_size * self.tier.target_occupation / forwarder.slot_size)

    def on_packet_access(self, env: Environment, packet: Packet, isWrite: bool):
        print("dram random length = " + len(self.tier.random_struct).__str__())
        # print("index length = " + len(self.forwarder.index.index).__str__())
        # print("dram random = " + self.tier.random_struct.__str__())
        # print(self.storage.index.__str__())
        if isWrite:
            if packet.name in self.tier.random_struct:
                print("data already in cache")
                return
            # free space if capacity full
            if len(self.tier.random_struct) >= self.nb_packets_capacity:
                old = self.tier.random_struct.pop(random.choice(list(self.tier.random_struct.keys())))
                print(old.name + " evicted from " + self.tier.name)

                # evict data
                self.tier.number_of_eviction_from_this_tier += 1
                self.tier.number_of_packets -= 1
                self.tier.used_size -= old.size

                # index update
                self.forwarder.index.del_packet(old.name)

                # print("index length after = " + len(self.forwarder.index.index).__str__())
                # store the removed packet from dram in disk ?
                try:
                    target_tier_id = self.forwarder.tiers.index(self.tier) + 1

                    # data is important or Disk is free
                    if self.forwarder.tiers[target_tier_id].submission_queue.__len__() != self.forwarder.tiers[
                            target_tier_id].submission_queue_max_size:
                        print("move data to disk " + old.name)
                        self.forwarder.tiers[target_tier_id].write_packet(env, old, cause='eviction')

                    # disk is overloaded --> drop packet
                    else:
                        print("drop packet" + old.name)
                except:
                    print("no other tier")

            # time
            yield env.timeout(
                self.tier.latency + packet.size / self.tier.write_throughput)
            self.tier.random_struct[packet.name] = packet

            # index update
            self.forwarder.index.update_packet_tier(packet.name, self.tier)
            self.tier.time_spent_writing += self.tier.latency + packet.size / self.tier.write_throughput

            # write data
            self.tier.used_size += packet.size
            self.tier.number_of_packets += 1
            self.tier.number_of_write += 1
        else:
            yield env.timeout(self.tier.latency + packet.size / self.tier.read_throughput)
            # time
            if packet.priority == 'l':
                self.tier.low_p_data_retrieval_time += Decimal(env.now) - packet.timestamp
            else:
                self.tier.high_p_data_retrieval_time += Decimal(env.now) - packet.timestamp
            self.tier.time_spent_reading += self.tier.latency + packet.size / self.tier.read_throughput

            # read a data
            self.tier.number_of_reads += 1
