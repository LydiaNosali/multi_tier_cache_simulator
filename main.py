import sys
import os
import time
import simpy
from plots.plot_creation import Plot
from simulation import Simulation
from traces.ndn_trace import NDNTrace
from forwarder_structures.pit import PIT
from forwarder_structures.tier import Tier
from forwarder_structures.index import Index
from forwarder import Forwarder
from policies.DRAM.pppolicy import PPPolicy
from policies.DRAM.dram_lru_policy import DRAMLRUPolicy
from policies.DRAM.dram_lfu_cache import DRAMLFUPolicy
from policies.DRAM.dram_random_policy import DRAMRandPolicy
from policies.DISK.lru_policy import LRUPolicy
from policies.DISK.lfu_policy import LFUPolicy
from policies.DISK.random_policy import RandPolicy

# time is in nanos
# size is in byte

# verify if the version of python is >3
if sys.version_info[0] < 3:
    raise Exception("Must be using Python 3")

# slot size allocation in dram and nvme
slot_size = 8000

# turn the trace into packets
trace = NDNTrace()
trace.gen_data()
# trace.gen_data(trace_len_limit=200000)

# number of requests on high priority content
nb_high_priority = [line for line in trace.data if line[4] == 'h'].__len__()
# number of requests on low priority content
nb_low_priority = [line for line in trace.data if line[4] == 'l'].__len__()
# total number of requests
nb_interests = len(trace.data)

# log files
output_folder = "logs/<timestamp>"
output_folder = output_folder.replace('/', os.path.sep).replace("<timestamp>",
                                                                time.strftime("%a_%d_%b_%Y_%H-%M-%S", time.localtime()))
output_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), output_folder))
try:
    os.makedirs(output_folder, exist_ok=True)
except:
    print(f'Error trying to create output folder "{output_folder}"')

# CS config
plot_content_store_config = []  # Content Store config str

# total size 1000kB
total_size = 1000000

# proportions
size_proportion = [1 / 10, 2 / 10, 3 / 10, 4 / 10]

# available policies
dramTierPolicies = [PPPolicy, DRAMLRUPolicy, DRAMLFUPolicy, DRAMRandPolicy]
diskTierPolicies = [LRUPolicy, LFUPolicy, RandPolicy]
# dramTierPolicies = [ARCPolicy]
# diskTierPolicies = [LRUPolicy]


for i in size_proportion:
    for dramPolicy in dramTierPolicies:
        for diskPolicy in diskTierPolicies:
            name = dramPolicy.__name__ + "+" + diskPolicy.__name__
            name = name.replace('Policy', '')
            name = name.replace('DRAM', '')
            name = name + "_" + i.__str__()
            print("=====================================")
            print(name)
            # Init simpy env
            env = simpy.Environment()
            # create the index
            index = Index()
            # Create the Content Store tiers
            # dram: max_size=100kB, latency = 100ns, read_throughput = 40GBPS, write_throughput = 20GBPS
            dram = Tier(name="DRAM", max_size=100000, granularity=1, latency=100, read_throughput=40,
                        write_throughput=20, target_occupation=0.6)
            # nvme: max_size=1000kB, latency = 10000ns, read_throughput = 3GBPS = 3Byte Per Nano Second
            # write_throughput = 1GBPS = 1Byte Per Nano Second
            nvme = Tier(name="NVMe", max_size=1000000, granularity=512, latency=10000, read_throughput=3,
                        write_throughput=1, target_occupation=1.0)
            tiers = [dram, nvme]
            # Create the PIT
            pit = PIT()
            # Create the forwarder
            forwarder = Forwarder(env, index, tiers, pit, slot_size)
            # Assign the policies
            dramPolicy(env, forwarder, dram)
            diskPolicy(env, forwarder, nvme)

            latest_filename = "latest" + name + ".log"
            sim = Simulation([trace], forwarder, env, log_file=os.path.join(output_folder, latest_filename),
                             logs_enabled=True)
            print("Starting simulation")
            last_results_filename = "json_data" + name + ".txt"
            last_results = sim.run()

            try:
                with open(os.path.join(output_folder, last_results_filename), "a") as f:
                    f.write(last_results)
            except:
                print(f'Error trying to write last_results into a new file in output folder "{output_folder}"')

            # CS config
            plot_content_store_config.append(name)

Plot(output_folder, plot_content_store_config, slot_size, nb_interests, nb_high_priority, nb_low_priority)
