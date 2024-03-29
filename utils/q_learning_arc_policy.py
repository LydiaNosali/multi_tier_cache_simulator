from collections import OrderedDict

from utils.q_learning_agent import QLearningAgent


class Deque(object):
    """Fast searchable queue"""

    def __init__(self):
        self.od = OrderedDict()

    def appendleft(self, k):
        if k in self.od:
            del self.od[k]
        self.od[k] = None

    def pop(self):
        return self.od.popitem(0)[0]

    def remove(self, k):
        del self.od[k]

    def __len__(self):
        return len(self.od)

    def __contains__(self, k):
        return k in self.od

    def __iter__(self):
        return reversed(self.od)

    def __repr__(self):
        return 'Deque(%r)' % (list(self),)


deque = Deque


class Cache(object):
    def __init__(self, size, learning_rate, discount_factor, epsilon):
        self.cached = {}  # Cache storage
        self.c = size  # Cache size
        self.p = 0  # Target size for the list T1

        # L1: only once recently
        self.t1 = deque()  # T1: recent cache entries
        self.b1 = deque()  # B1: ghost entries recently evicted from the T1 cache

        # L2: at least twice recently
        self.t2 = deque()  # T2: frequent entries
        self.b2 = deque()  # B2: ghost entries recently evicted from the T2 cache

        # Init the Q-Learning Agent
        self.q_learning_agent = QLearningAgent(self.c, self.c, learning_rate, discount_factor, epsilon)
        self.cache_hit = 0
        self.b1_hit = 0
        self.b2_hit = 0
        self.request = 0
        self.p_table = []
        self.p_table.append(self.p)

    def replace(self, args):
        """
        If (T1 is not empty) and ((T1 lenght exceeds the target p) or (x is in B2 and T1 lenght == p))
            Delete the LRU page in T1 (also remove it from the cache), and move it to MRU position in B1.
        else
            Delete the LRU page in T2 (also remove it from the cache), and move it to MRU position in B2.
        endif
        """

        if self.t1 and ((args in self.b2 and len(self.t1) == self.p) or (len(self.t1) > self.p)):
            old = self.t1.pop()
            self.b1.appendleft(old)
        else:
            old = self.t2.pop()
            self.b2.appendleft(old)

        del self.cached[old]

    def on_packet_access(self, args):
        self.request += 1
        # Case I: x is in T1 or T2.
        #  A cache hit has occurred in MARC(c) and DBL(2c)
        #   Move x to MRU position in T2.

        if args in self.t1:
            self.cache_hit += 1
            self.p = self.q_learning_agent.get_next_state(self.p, len(self.t1), len(self.b1), len(self.b2), "t1")
            self.p_table.append(self.p)
            self.t1.remove(args)
            self.t2.appendleft(args)
            return self.cached[args]

        if args in self.t2:
            self.cache_hit += 1
            self.p = self.q_learning_agent.get_next_state(self.p, len(self.t1), len(self.b1), len(self.b2), "t2")
            self.p_table.append(self.p)
            self.t2.remove(args)
            self.t2.appendleft(args)
            return self.cached[args]

        result = args
        self.cached[args] = result

        # Case II: x is in B1
        #  A cache miss has occurred in MARC(c)
        #   ADAPTATION
        #   REPLACE(x)
        #   Move x from B1 to the MRU position in T2 (also fetch x to the cache).

        if args in self.b1:
            self.b1_hit += 1
            self.p = self.q_learning_agent.get_next_state(self.p, len(self.t1), len(self.b1), len(self.b2), "b1")
            self.p_table.append(self.p)

            self.replace(args)
            self.b1.remove(args)
            self.t2.appendleft(args)
            return result

        # Case III: x is in B2
        #  A cache miss has (also) occurred in MARC(c)
        #   ADAPTATION
        #   REPLACE(x, p)
        #   Move x from B2 to the MRU position in T2 (also fetch x to the cache).

        if args in self.b2:
            self.b2_hit += 1
            self.p = self.q_learning_agent.get_next_state(self.p, len(self.t1), len(self.b1), len(self.b2), "b2")
            self.p_table.append(self.p)

            self.replace(args)
            self.b2.remove(args)
            self.t2.appendleft(args)
            return result

        # Case IV: x is not in (T1 u B1 u T2 u B2)
        #  A cache miss has occurred in MARC(c) and DBL(2c)
        self.p = self.q_learning_agent.get_next_state(self.p, len(self.t1), len(self.b1), len(self.b2), "Miss")
        self.p_table.append(self.p)
        if len(self.t1) + len(self.b1) == self.c:
            # Case A: L1 (T1 u B1) has exactly c pages.

            if len(self.t1) < self.c:
                # Delete LRU page in B1. REPLACE(x, p)
                self.b1.pop()
                self.replace(args)
            else:
                # Here B1 is empty.
                # Delete LRU page in T1 (also remove it from the cache)
                del self.cached[self.t1.pop()]

        else:
            # Case B: L1 (T1 u B1) has less than c pages.
            total = len(self.t1) + len(self.b1) + len(self.t2) + len(self.b2)
            if total >= self.c:
                # Delete LRU page in B2, if |T1| + |T2| + |B1| + |B2| == 2c
                if total == (2 * self.c):
                    self.b2.pop()

                # REPLACE(x, p)
                self.replace(args)

        # Finally, fetch x to the cache and move it to MRU position in T1
        self.t1.appendleft(args)
        return result
