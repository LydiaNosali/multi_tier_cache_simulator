# import csv
import random
import time

import numpy as np

from common.packet import Packet
from common.zipf import zipf_distribution


# time is in second
# size is in byte
# 'data_back', 'timestamp', 'name', 'size', 'priority', 'InterestLifetime', 'response_time'


class TraceCreator:
    def __init__(self, n_unique_items: int, high_priority_content_percentage: float, pareto_alpha: float,
                 zipf_alpha: float, poisson_lambda: float,
                 min_data_size: int, max_data_size: int,
                 min_data_rtt: float, max_data_rtt: float,
                 interest_lifetime: float, traffic_period: int):
        """"
        :param n_unique_items: number of unique items
        "param high_priority_content_percentage: portion of high priority content
        :param zipf_alpha: alpha of the distribution Zipf
        :param poisson_lambda: lambda of the poisson distribution
        :param min_data_size: minimum data size octets
        :param max_data_size: maximum data size octets
        :param min_data_rtt: minimum response time for an interest in s
        :param max_data_rtt: maximum response time for an interest in s
        :param interest_lifetime: interest life time in s
        :param traffic_period: in minutes
        """""
        start_time = time.time()
        print("Start creating the trace at: " + start_time.__str__())

        # generate a catalog of items. Assign each item a size
        unique_words = dict()
        for i in range(n_unique_items):
            size = int(round(np.random.uniform(min_data_size, max_data_size), 0))
            priority = "h" if random.random() < high_priority_content_percentage else "l"
            response_time = np.random.uniform(min_data_rtt, max_data_rtt)
            packet = Packet("d", 0, i.__str__(), size, priority, response_time)
            unique_words[i] = packet

        with open('../resources/dataset_synthetic/synthetic-'
                  + n_unique_items.__str__() + "_" + poisson_lambda.__str__()
                  + "_" + zipf_alpha.__str__() + "_" + high_priority_content_percentage.__str__()
                  + "_" + traffic_period.__str__() + '.csv',
                  'w', encoding="utf-8",
                  newline='') as trace_file:

            req_time = 0
            while req_time < traffic_period * 60:
                # select a request time following poisson distribution
                # req_time = req_time + np.random.uniform(0.01, 0.2)
                req_time = req_time + random.expovariate(poisson_lambda)
                # index = int(np.random.pareto(pareto_alpha) % len(unique_words))
                # print("index %s" % index)
                # while index >= len(unique_words):
                #     index = int(np.random.pareto(pareto_alpha) % len(unique_words))
                # choose an item using the zipf distribution
                index = zipf_distribution(zipf_alpha, len(unique_words))
                while index >= len(unique_words):
                    index = zipf_distribution(zipf_alpha, len(unique_words))
                # write the request to the trace file
                trace_file.write(
                    "{},{},{},{},{},{},{}\n".format("d", req_time, unique_words[index].name, unique_words[index].size,
                                                    unique_words[index].priority, interest_lifetime,
                                                    unique_words[index].response_time))

        creation_time = time.time() - start_time
        print("trace creation took : %s " % creation_time)

        # with open('../resources/time/synthetic- '
        #           + n_unique_items.__str__() + "_" + poisson_lambda.__str__()
        #           + "_" + zipf_alpha.__str__() + "_" + high_priority_content_percentage.__str__() + "_"
        #           + traffic_period.__str__() + "_" + "time" + '.csv',
        #           'w', encoding="utf-8", newline='') as f:
        #     writer = csv.writer(f)
        #     writer.writerow("Trace creation took: " + creation_time.__str__())

# def pareto_distribution(alpha, size):
#     """Generate random samples from a Pareto distribution.
#
#     Parameters:
#         alpha (float): The shape parameter of the distribution. Must be > 0.
#         size (int or tuple of ints): The shape of the output. If it is an int, then the output will be a 1D array of
#         that length.
#
#     Returns:
#         ndarray or scalar: Drawn samples from the distribution.
#     """
#     return np.random.pareto(alpha, size) - 1
