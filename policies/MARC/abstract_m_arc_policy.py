import math

from simpy.core import Environment

from common.deque import Deque
from common.packet import Packet
from forwarder_structures.content_store.tier import Tier
from forwarder_structures.forwarder import Forwarder
from policies.policy import Policy


class AbstractMARCPolicy(Policy):
    def __init__(self, env: Environment, forwarder: Forwarder, tier: Tier):
        Policy.__init__(self, env, forwarder, tier)

        self.c = self.c()  # cache size

        self.p = 0  # Target size for the list T1
        self.t1 = self.t1()  # T1: recent cache entries
        self.t2 = self.t2()  # T2: frequent entries

        self.beta_ssd = self.forwarder.get_next_tier(1).max_size / self.forwarder.get_default_tier().max_size
        self.beta_disk = self.forwarder.get_next_tier(2).max_size / self.forwarder.get_default_tier().max_size

    def _replace(self, env: Environment, packet: Packet):
        in_b2 = yield env.process(self.forwarder.index.packet_in_ghost(packet.name, 'b2'))
        if self.t1 and ((in_b2 and len(self.t1) == self.p) or (len(self.t1) > self.p)):
            old_name, old = self.t1.get_without_pop()
            self.t1_pop(old)
            print("%s move from t1 to b1 " % old.name)
            yield env.process(self.forwarder.index.del_packet_from_cs(old.name))
            yield env.process(self.forwarder.index.update_packet_ghost(old.name, 'b1'))
        else:
            old_name, old = self.t2.get_without_pop()
            self.t2_pop(old)
            print("%s move from t2 to b2 " % old.name)
            yield env.process(self.forwarder.index.del_packet_from_cs(old.name))
            yield env.process(self.forwarder.index.update_packet_ghost(old.name, 'b2'))

    def on_packet_access(self, env: Environment, res, packet: Packet, is_write: bool):
        print('%s in %s' % (self.tier.name, env.now))
        if self.c == 0:
            print("cache units == %s" % self.c)
            return

        if not is_write and self.t1.__contains__(packet.name):
            print("%s hit in t1, promote to MRU t2" % packet.name)
            self.t1_remove(packet)
            yield env.process(self.t2_append_left(env, res, packet))

            self.t1.__str__()
            self.t2.__str__()
            self.forwarder.index.__str__()
            self.forwarder.index.__str__(what="Ghost")
            print('%s out of %s' % (self.tier.name, env.now))
            return

        if not is_write and self.t2.__contains__(packet.name):
            print("%s hit in t2, promote to MRU t2" % packet.name)
            self.t2_remove(packet)
            yield env.process(self.t2_append_left(env, res, packet))

            self.t1.__str__()
            self.t2.__str__()
            self.forwarder.index.__str__()
            self.forwarder.index.__str__(what="Ghost")
            print('%s out of %s' % (self.tier.name, env.now))
            return

        in_b1 = yield env.process(self.forwarder.index.packet_in_ghost(packet.name, 'b1'))
        if in_b1:
            len_b1 = yield env.process(self.forwarder.index.ghost_len('b1'))
            len_b2 = yield env.process(self.forwarder.index.ghost_len('b2'))
            self.increment_p(len_b1, len_b2)
            yield env.process(self._replace(env, packet))
            yield env.process(self.forwarder.index.del_packet_from_ghost(packet.name))
            print("%s hit in b1, promote to MRU t2" % packet.name)
            yield env.process(self.t2_append_left(env, res, packet))

            self.t1.__str__()
            self.t2.__str__()
            self.forwarder.index.__str__()
            self.forwarder.index.__str__(what="Ghost")
            print('%s out of %s' % (self.tier.name, env.now))
            return

        in_b2 = yield env.process(self.forwarder.index.packet_in_ghost(packet.name, 'b2'))
        if in_b2:
            len_b1 = yield env.process(self.forwarder.index.ghost_len('b1'))
            len_b2 = yield env.process(self.forwarder.index.ghost_len('b2'))
            self.decrement_p(len_b1, len_b2)
            yield env.process(self._replace(env, packet))
            yield env.process(self.forwarder.index.del_packet_from_ghost(packet.name))
            print("%s hit in b2, promote to MRU t2" % packet.name)
            yield env.process(self.t2_append_left(env, res, packet))

            self.t1.__str__()
            self.t2.__str__()
            self.forwarder.index.__str__()
            self.forwarder.index.__str__(what="Ghost")
            print('%s out of %s' % (self.tier.name, env.now))
            return

        len_b1 = yield env.process(self.forwarder.index.ghost_len('b1'))
        if len(self.t1) + len_b1 == self.c:
            print("%s cache miss in all queues" % packet.name)
            # Case A: L1 (T1 u B1) has exactly c pages.
            if len(self.t1) < self.c:
                print("evict from b1")
                yield env.process(self.forwarder.index.pop_packet_from_ghost('b1'))
                yield env.process(self._replace(env, packet))
            else:
                name, old = self.t1.get_without_pop()
                self.t1_pop(old)
                print("%s evict from t1" % old.name)
                yield env.process(self.forwarder.index.del_packet_from_cs(old.name))
        else:
            len_b1 = yield env.process(self.forwarder.index.ghost_len('b1'))
            len_b2 = yield env.process(self.forwarder.index.ghost_len('b2'))
            total = len(self.t1) + len_b1 + len(self.t2) + len_b2
            if total >= self.c:
                if total == (2 * self.c):
                    print("evict from b2")
                    yield env.process(self.forwarder.index.pop_packet_from_ghost('b2'))
                yield env.process(self._replace(env, packet))

        print("%s write to MRU t1" % packet.name)
        yield env.process(self.t1_append_left(env, res, packet))

        self.t1.__str__()
        self.t2.__str__()
        self.forwarder.index.__str__()
        self.forwarder.index.__str__(what="Ghost")
        print('%s out of %s' % (self.tier.name, env.now))
        return

    def t1(self):
        t1 = Deque()
        for tier in self.forwarder.tiers[1:]:
            for strategy in tier.strategies:
                try:
                    t1.update(strategy.t1)
                except Exception as e:
                    print(e)
        return t1

    def t2(self):
        t2 = Deque()
        for tier in self.forwarder.tiers[1:]:
            for strategy in tier.strategies:
                try:
                    t2.update(strategy.t2)
                except Exception as e:
                    print(e)
        return t2

    def c(self):
        c = 0
        for tier in self.forwarder.tiers[1:]:
            c += math.trunc(tier.max_size * tier.target_occupation / self.forwarder.slot_size)
        return c

    def t1_pop(self, old):
        self.t1.pop()
        for tier in reversed(self.forwarder.tiers[1:]):
            for strategy in tier.strategies:
                try:
                    if strategy.t1:
                        strategy.t1.remove(old.name)
                        # evict data
                        tier.number_of_eviction_from_this_tier += 1
                        tier.number_of_packets -= 1
                        tier.used_size -= old.size
                        break
                except Exception as e:
                    print(e)

    def t2_pop(self, old):
        self.t2.pop()
        for tier in reversed(self.forwarder.tiers[1:]):
            for strategy in tier.strategies:
                try:
                    if strategy.t2:
                        strategy.t2.remove(old.name)
                        # evict data
                        tier.number_of_eviction_from_this_tier += 1
                        tier.number_of_packets -= 1
                        tier.used_size -= old.size
                        break
                except Exception as e:
                    print(e)

    def t1_remove(self, packet):
        self.t1.remove(packet.name)
        for tier in self.forwarder.tiers[1:]:
            for strategy in tier.strategies:
                try:
                    if packet.name in strategy.t1:
                        strategy.t1.remove(packet.name)
                        tier.number_of_eviction_from_this_tier += 1
                        tier.number_of_packets -= 1
                        tier.used_size -= packet.size
                        break
                except Exception as e:
                    print(e)

    def t2_remove(self, packet):
        self.t2.remove(packet.name)
        for tier in self.forwarder.tiers[1:]:
            for strategy in tier.strategies:
                try:
                    if packet.name in strategy.t2:
                        strategy.t2.remove(packet.name)
                        tier.number_of_eviction_from_this_tier += 1
                        tier.number_of_packets -= 1
                        tier.used_size -= packet.size
                        break
                except Exception as e:
                    print(e)

    def t1_append_left(self, env, res, packet):
        self.t1.append_left(packet.name, packet)
        yield env.process(self.forwarder.get_default_tier().write_packet_t1(env, res, packet))

    def t2_append_left(self, env, res, packet):
        self.t2.append_left(packet.name, packet)
        yield env.process(self.forwarder.get_default_tier().write_packet_t2(env, res, packet))

    def increment_p(self, len_b1, len_b2):
        self.p = min(self.c, self.p + max((len_b2 / len_b1) * (1 + self.beta_ssd + self.beta_disk),
                                          1 + self.beta_ssd + self.beta_disk))
        for strategy in self.forwarder.get_default_tier().strategies:
            try:
                strategy.p = min(strategy.c, strategy.p + max(len_b2 / len_b1, 1))
                break
            except Exception as e:
                print(e)
        for strategy in self.forwarder.get_next_tier(1).strategies:
            try:
                strategy.p = min(strategy.c, strategy.p + max((len_b2 / len_b1) * self.beta_ssd, self.beta_ssd))
                break
            except Exception as e:
                print(e)
        for strategy in self.forwarder.get_next_tier(2).strategies:
            try:
                strategy.p = min(strategy.c, strategy.p + max((len_b2 / len_b1) * self.beta_disk, self.beta_disk))
                break
            except Exception as e:
                print(e)

    def decrement_p(self, len_b1, len_b2):
        self.p = max(0, self.p - max((len_b1 / len_b2) * (1 + self.beta_ssd + self.beta_disk),
                                     1 + self.beta_ssd + self.beta_disk))
        for strategy in self.forwarder.get_default_tier().strategies:
            try:
                strategy.p = max(0, strategy.p - max((len_b1 / len_b2), 1))
                break
            except Exception as e:
                print(e)
        for strategy in self.forwarder.get_next_tier(1).strategies:
            try:
                strategy.p = max(0, strategy.p - max((len_b1 / len_b2) * self.beta_ssd, self.beta_ssd))
                break
            except Exception as e:
                print(e)
        for strategy in self.forwarder.get_next_tier(2).strategies:
            try:
                strategy.p = max(0, strategy.p - max((len_b1 / len_b2) * self.beta_disk, self.beta_disk))
                break
            except Exception as e:
                print(e)
