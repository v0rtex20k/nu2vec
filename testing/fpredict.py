import argparse
import scipy.spatial.distance as dist
import numpy as np
import networkx as nx
import random

"""
Current TODOs:
  - Only chooses best label, output list of l abels with significance
  - Argument parsing is a code smell. I don't like it.
"""

"""
Parses the arguments into an arguments object.
"""
def parse_args():
    p = argparse.ArgumentParser(description="Function prediction.")
    p.add_argument("network", help="Network file.")
    p.add_argument("labels", help="Node labels file.")
    p.add_argument("--network-type", "-t", required=True,
                   choices=["edgelist", "weighted_edgelist",
                            "embedding", "string"],
                   help="Type of network file.")
    p.add_argument("--algorithm", "-a", required=True,
                   choices=["mv", "wmv", "knn"],
                   help="Function prediction algorithm to use.")
    p.add_argument("--cross-validate", type=int,
                   help="Assumes label list is full and performs k-fold "
                        "cross validation.")
    p.add_argument("--args", nargs='*',
                   help="Extra arguments for prediction algorithm.")
    return p.parse_args()

"""
Takes a node-labels text file and outputs a
dictionary mapping label node name to a list
of labels.
"""
def parse_labels(fname):
    node_name_to_labels = {}

    with open(fname, "r") as f:
        lines = f.readlines()
        for line in lines:
            words = line.split()
            name = words[0]
            labels = words[1:]
            node_name_to_labels[name] = labels

    return node_name_to_labels

"""
Takes a node2vec embedding file and outputs
both a NxD matrix and an array where the ith
entry contains the name of the node in the ith
row of the matrix.
"""
def parse_embedding(fname):
    with open(fname, "r") as f:
        lines = f.readlines()

        dimensions = lines[0].split()
        n = int(dimensions[0])
        d = int(dimensions[1])

        matrix = np.empty([n, d])
        node_name_array = [None] * n
        for i in range(n):
            line = lines[i + 1]
            words = line.split()

            name = words[0]
            values = list(map(float, words[1:]))
            matrix[i] = values
            node_name_array[i] = name

        return (matrix, node_name_array)

"""
Parses the STRING network file into a weighted networkx
graph using the specified column as the weights.

Reference file format is 4932.protein.links.detailed.v11.0.txt
"""
def parse_string_network(fname, column):
    graph = nx.Graph()

    with open(fname, "r") as f:
        lines = f.readlines()
        for line in lines[1:]:
            words = line.split()

            protein1 = words[0][5:]
            protein2 = words[1][5:]
            weight = float(words[column + 2])

            graph.add_edge(protein1, protein2, weight=weight)

    return graph

"""
Parses the network file using the appropriate method.
"""
def parse_network(args):
    if args.network_type == "edgelist":
        return nx.readwrite.edgelist.read_edgelist(args.network)
    elif args.network_type == "weighted_edgelist":
        return nx.readwrite.edgelist.read_weighted_edgelist(args.network)
    elif args.network_type == "embedding":
        return parse_embedding(args.network)
    elif args.network_type == "string":
        return parse_string_network(args.network, args.string)

"""
Returns most popular label among the voters,
optionally weighted by their significance.
"""
def vote(voters, labels, weights=None):
    label_counts = {}

    for voter in voters:
        for label in labels[voter]:
            weight = 1
            if weights is not None:
                weight = weights[voter]

            if label not in label_counts:
                label_counts[label] = weight
            else:
                label_counts[label] += weight

    return max(label_counts, key=lambda k: label_counts[k])

"""
Uses k-nearest neighbors to vote for
the label on unlabeled nodes.

Outputs a labelling for the nodes.
"""
def knn(matrix, node_names, labels, k):
    labelling = {}

    distances = dist.squareform(dist.pdist(matrix))

    for i in range(len(matrix)):
        node = node_names[i]

        if node in labels:
            labelling[node] = labels[node]
            continue

        sorted_voter_ids = np.argsort(distances[i])[1:]

        voters = []

        j = 0
        while len(voters) < k or j >= len(sorted_voter_ids):
            potential_voter = node_names[j]
            if potential_voter in labelling:
                voters.append(potential_voter)
            j = j + 1

        label = vote(voters, labels)
        labelling[node] = [label]

    return labelling

"""
Performs majority vote on unlabeled nodes
in the graph.

Outputs a labelling for the nodes.
"""
def mv(G, labels, weighted=False):
    labelling = {}

    for node in G.nodes():
        if node in labels:
            labelling[node] = labels[node]
            continue

        voters = list(G[node])
        if weighted:
            weights = {}

            for (voter, data) in G[node].items():
                weights[voter] = data["weight"]

            label = vote(voters, labels, weights=weights)
            labelling[node] = [label]
        else:
            label = vote(voters, labels)
            labelling[node] = [label]

    return labelling

"""
Runs algorithm, returns labelling.
"""
def run_algorithm(labels, args):
    if args.algorithm == "mv":
        graph = parse_network(args)
        return mv(graph, labels, weighted=False)
    elif args.algorithm == "wmv":
        graph = parse_network(args)
        return mv(graph, labels, weighted=True)
    elif args.algorithm == "knn":
        try:
            k = int(args.args[0])
        except TypeError:
            print("Expected argument for k-nearest neighbors.")
            exit(1)
        except ValueError:
            print("Expected integer argument.")
            exit(1)

        (mat, nna) = parse_network(args)
        return knn(mat, nna, labels, k)

if __name__ == "__main__":
    args = parse_args()
    labels = parse_labels(args.labels)

    if args.cross_validate is not None:
        nodes = list(labels.keys())
        random.shuffle(nodes)

        """ Remove n / k nodes from labelling and run algorithm on
            each set. """
        for i in range(0, args.cross_validate):
            inc = int(len(nodes) / args.cross_validate)

            training_nodes = nodes[:inc * i] + nodes[inc * (i + 1):]
            training_labels = {}
            for n in training_nodes:
                if n in labels:
                    training_labels[n] = labels[n]

            test_labelling = run_algorithm(training_labels, args)
    else:
        labelling = run_algorithm(labels, args)

        """ Print labelling to stdout """
        for node, labels in labelling.items():
            labels_str = " ".join(labels)
            print(node + " " + labels_str)

    exit(0)
