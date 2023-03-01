import os

import simpy

from simulation import Simulation
from forwarder_structures.pit import PIT
from forwarder_structures.content_store.tier import Tier
from forwarder_structures.content_store.index import Index
from forwarder import Forwarder


def arc_main(boss_policy, dram_policy, disk_policy, slot_size, size_proportion, total_size, trace, output_folder):
    for i in size_proportion:
        name = "ARC_" + i.__str__()
        print("=====================================")
        print(name)

        # Init simpy env
        env = simpy.Environment()

        # create the index
        index = Index(env)

        # Create the Content Store tiers
        boss = Tier(name="Boss", max_size=0, granularity=0, latency=0,
                    read_throughput=0, write_throughput=0, target_occupation=0)

        # dram: max_size=100kB, latency = 100ns = 1e-7s, read_throughput = 40GBPS, write_throughput = 20GBPS
        dram = Tier(name="DRAM", max_size=int(total_size * i), granularity=1, latency=1e-7,
                    read_throughput=40000000000, write_throughput=20000000000, target_occupation=1)

        # nvme: max_size=1000kB, latency = 10000ns, read_throughput = 3GBPS = 3Byte Per Nano Second
        # write_throughput = 1GBPS = 1Byte Per Nano Second
        disk = Tier(name="NVMe", max_size=int(total_size - total_size * i), granularity=512, latency=1e-5,
                    read_throughput=3000000000, write_throughput=1000000000, target_occupation=1.0)

        tiers = [boss, dram, disk]

        # Create the PIT
        pit = PIT()

        # Create the forwarder
        forwarder = Forwarder(env, index, tiers, pit, slot_size, default_tier_index=1)

        # Assign the policies
        boss_policy(env, forwarder, boss)
        dram_policy(env, forwarder, dram)
        disk_policy(env, forwarder, disk)

        latest_filename = "latest" + name + ".log"
        sim = Simulation([trace], forwarder, env, log_file=os.path.join(output_folder, latest_filename),
                         logs_enabled=True)
        print("Starting simulation")
        last_results_filename = name + ".txt"
        last_results = sim.run()
        try:
            with open(os.path.join(output_folder, last_results_filename), "a") as f:
                f.write(last_results)
        except Exception as e:
            print(f'Error %s trying to write last_results into a new file in output folder "{output_folder}"' % e)


def policy_main(dram_policy, disk_policy, slot_size, size_proportion, total_size, trace,
                output_folder):
    for i in size_proportion:
        name = dram_policy.__name__ + "_" + i.__str__() + "_" + trace.__class__.__name__
        name = name.replace('Policy', '')
        name = name.replace('DRAM', '')
        print("=====================================")
        print(name)

        # Init simpy env
        env = simpy.Environment()

        # create the index
        index = Index(env)

        # Create the Content Store tiers
        # dram: max_size=100kB, latency = 100ns = 1e-7s, read_throughput = 40GBPS, write_throughput = 20GBPS
        dram = Tier(name="DRAM", max_size=int(total_size * i), granularity=1, latency=1e-7,
                    read_throughput=40000000000, write_throughput=20000000000, target_occupation=1)
        # nvme: max_size=1000kB, latency = 10000ns, read_throughput = 3GBPS = 3Byte Per Nano Second
        # write_throughput = 1GBPS = 1Byte Per Nano Second
        disk = Tier(name="NVMe", max_size=int(total_size - total_size * i), granularity=512, latency=1e-5,
                    read_throughput=3000000000, write_throughput=1000000000, target_occupation=1.0)

        tiers = [dram, disk]

        # Create the PIT
        pit = PIT()

        # Create the forwarder
        forwarder = Forwarder(env, index, tiers, pit, slot_size, default_tier_index=0)

        # Assign the policies
        dram_policy(env, forwarder, dram)
        disk_policy(env, forwarder, disk)

        latest_filename = "latest" + name + ".log"
        sim = Simulation([trace], forwarder, env, log_file=os.path.join(output_folder, latest_filename),
                         logs_enabled=True)
        print("Starting simulation")
        last_results_filename = name + ".txt"
        last_results = sim.run()
        try:
            with open(os.path.join(output_folder, last_results_filename), "a") as f:
                f.write(last_results)
        except Exception as e:
            print(f'Error %s trying to write last_results into a new file in output folder "{output_folder}"' % e)