import math
from policies.policy import Policy
from storage_structures import StorageManager, Tier
from simpy.core import Environment


class LFUPolicy(Policy):
    def __init__(self, tier: Tier, storage: StorageManager, env: Environment):
        Policy.__init__(self, tier, storage, env)
        self.__capa = math.trunc(self.tier.max_size * self.tier.target_occupation / 16777216)

    def on_packet_access(self, tstart_tlast: int, name: str, size: int, priority: str, isWrite: bool,
                         drop="n"):
        print("==========================")
        print("disk LFU = " + self.tier.key_to_freq.items().__str__())
        print("disk index = " + self.storage.index.index.__str__())
        print("==========================")
        if isWrite:
            if self.__capa <= 0:
                print("error cache has no memory")
                return
            print("Writing \"" + name.__str__() + "\" to " + self.tier.name.__str__())
            # key not in key_to_freq and size == capacity --> free space
            if name not in self.tier.key_to_freq and self.tier.number_of_packets == self.__capa:
                print("key not in self.__key_to_freq and == self.__capa")
                del self.tier.key_to_freq[self.tier.freq_to_nodes[self.tier.min_freq].popitem(last=False)[0]]
                if not self.tier.freq_to_nodes[self.tier.min_freq]:
                    del self.tier.freq_to_nodes[self.tier.min_freq]
                self.tier.number_of_packets -= 1
                self.tier.used_size -= size
            self.update(name, size, priority, drop)
            # index update
            self.storage.index.update_packet_tier(name, self.tier)
            # time
            if tstart_tlast > self.tier.last_completion_time:
                self.tier.time_spent_writing += self.tier.latency + size / self.tier.throughput
                self.tier.last_completion_time = self.tier.latency + size / self.tier.throughput
            else:
                self.tier.time_spent_writing += self.tier.last_completion_time - tstart_tlast + self.tier.latency \
                                                + size / self.tier.throughput
                self.tier.last_completion_time = self.tier.last_completion_time - tstart_tlast + self.tier.latency \
                                                 + size / self.tier.throughput
            # write data
            self.tier.number_of_write += 1
        else:  # get
            if name not in self.tier.key_to_freq:
                print("data not in cache")
                return -1
            print("Reading \"" + name.__str__() + "\" from " + self.tier.name.__str__())
            self.tier.chr += 1  # chr

            priority = self.tier.freq_to_nodes[self.tier.key_to_freq[name]][name]
            self.update(name, size, priority, drop)
            # time
            if tstart_tlast > self.tier.last_completion_time:
                self.tier.time_spent_reading += self.tier.latency + size / self.tier.throughput
                self.tier.last_completion_time = self.tier.latency + size / self.tier.throughput
            else:
                self.tier.time_spent_reading += self.tier.last_completion_time - tstart_tlast + self.tier.latency \
                                                + size / self.tier.throughput
                self.tier.last_completion_time = self.tier.last_completion_time - tstart_tlast + self.tier.latency \
                                                 + size / self.tier.throughput
            # read a data
            self.tier.number_of_reads += 1

    def update(self, name, size, priority, drop):
        freq = 0
        if name in self.tier.key_to_freq:
            freq = self.tier.key_to_freq[name]
            del self.tier.freq_to_nodes[freq][name]
            if not self.tier.freq_to_nodes[freq]:
                del self.tier.freq_to_nodes[freq]
                if self.tier.min_freq == freq:
                    self.tier.min_freq += 1
            self.tier.number_of_packets -= 1
            self.tier.used_size -= size

        freq += 1
        self.tier.min_freq = min(self.tier.min_freq, freq)
        self.tier.key_to_freq[name] = freq
        self.tier.freq_to_nodes[freq][name] = priority
        self.tier.number_of_packets += 1
        self.tier.used_size += size
