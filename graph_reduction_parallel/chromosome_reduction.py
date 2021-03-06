"""
Each chromosome is treated as a single graph, and they are reduced seperatedly.
"""
import argparse
import numpy as np
from graph_reduction_parallel import load_graph
from graph_reduction_parallel import filter_edges
from graph_reduction_parallel import load_patient
from graph_reduction_parallel import merge_edges
import sys
import networkx as nx
import pandas as pd


def get_args():
    parser = argparse.ArgumentParser('python')

    parser.add_argument('-edge_dir',
                        #default='../../processed_main_graph/final_edge.h5',
                        default='../../test_data/test_1.h5',
                        required=False,
                        help='directory of output edge file.')  

    parser.add_argument('-node_dir',
                        #default='../../processed_main_graph/final_node.csv',
                        default='../../test_data/test_1.csv',
                        required=False,
                        help='directory of output edge file.')  

    parser.add_argument('-snps_dir',
                        default='../../snp_map/snp_map.json',
                        required=False,
                        help='location of the snp mapping file.') 

    parser.add_argument('-patient_dir',
                        default='../../patients/BCAC-97446542.csv',
                        required=False,
                        help='location of the patient file.') 

    parser.add_argument('-snp_weight_dir',
                        default='../../snp_weight/PRS_SNPs',
                        required=False,
                        help='csv file containing weights of snps') 

    parser.add_argument('-verbose',
                        default=0,
                        required=False,
                        help='set to 1 for debugging.')

    parser.add_argument('-reduced_node_dir',
                        #default='../../patients_reduced/BCAC-97446542-node.csv',
                        default='../../test_data_reduced/reduced_node_test_1_4.csv',
                        required=False,
                        help='csv file of reduced node table.') 

    parser.add_argument('-reduced_edge_dir',
                        #default='../../patients_reduced/BCAC-97446542-edge.csv',
                        default='../../test_data_reduced/reduced_edge_test_1_4.csv',
                        required=False,
                        help='csv file of reduced node table.') 

    parser.add_argument('-reduced_chr_dir',
                        #default='../../patients_reduced/BCAC-97446542.gexf',
                        default='../../chr_data_reduced/',
                        required=False,
                        help='csv file of reduced node table.') 

    parser.add_argument('-reduced_graph_statistics',
                        #default='../../patients_reduced/BCAC-97446542-statistics.json',
                        default='../../test_data_reduced/reduced_gexf_statistics_test_1_4.csv',
                        required=False,
                        help='csv file of reduced node table.') 

    parser.add_argument('-chr',
                        default=1,
                        required=False,
                        help='which chromosome to compute')       

    return parser.parse_args()


def merge_chr_nodes(nodes_array_chr):
    """
    Merge the nodes of a single chromosome. 
    nodes_array: numpy array containing all nodes of the patient. It has the following columns:
        [node-id, chromosome, chunk_start, chunk_end, has_snp]
    chr: chromosome number.
    
    A new column 'new_merged' will be added in the merging process. 0 indicates an old node while 1
    indicates a new merged node.
    """
    '''compute nodes to merge for this chromosome'''
    to_merge = []
    merged_node = []
    for row in nodes_array_chr: # for each row in this chromosome
        #print(row)
        if row[4]==0:
            merged_node.append(row[0]) # append node id to merge
        elif row[4]==1:
            if len(merged_node) > 1: # counted as merged on when there are at least 2 nodes in the list
                to_merge.append(merged_node)
            merged_node = []
        else:
            raise ValueError('has_snp column should be either integer of 1 or 0')
    if len(merged_node) > 1: # counted as merged on when there are at least 2 nodes in the list
        to_merge.append(merged_node)

    '''compute merged node table for this chromosome'''
    nodes_array_copy = nodes_array_chr # nodes of corresponding chromosomes
    idx_to_remove = []
    for old_nodes in to_merge: # difficult to parallelize because processes will be modifying shared array.
        for old_node in old_nodes:
            idx = np.nonzero(nodes_array_copy[:,0]==old_node)
            idx_to_remove.append(idx[0].item())
    idx_to_remove = np.array(idx_to_remove)
    nodes_array_copy = np.delete(nodes_array_copy, idx_to_remove, 0) # delete the nodes to merge
    nodes_array_copy = np.hstack([nodes_array_copy, np.zeros([nodes_array_copy.shape[0], 1]).astype(int)]) # add a column of zeros for 'new_merged' feature

    unchanged_nodes = list(nodes_array_copy[:,0]) # keys also contents for unchanged nodes
    old_to_new_dict_total = dict(zip(unchanged_nodes, unchanged_nodes)) # update the dictionary for edge reduction
    new_to_old_dict_total = dict(zip(unchanged_nodes, unchanged_nodes)) # same for unchanged nodes

    if len(to_merge)>0: 
        old_to_new_dict = {}
        new_nodes = []
        for nodes in to_merge:
            nodes_array_sub = [] # get sub-array of nodes to merge
            for node in nodes: # get the corresponding sub-array node table
                nodes_array_sub.append(nodes_array_chr[np.nonzero(nodes_array_chr[:,0]==node)])
            nodes_array_sub = np.concatenate(nodes_array_sub)
            new_node_id = nodes_array_sub[0, 0] # use first old node id as merged node id
            chromosome =  nodes_array_sub[0, 1] # chromosome of new node
            chunk_start = np.amin(nodes_array_sub[:, 2]) # chunk_start of new node
            chunk_end = np.amax(nodes_array_sub[:, 3])# chunk_end of new node
            for node in nodes: # update the old to new node dictionary
                old_to_new_dict[node] = new_node_id
            new_nodes.append(np.array([new_node_id, chromosome, chunk_start, chunk_end, 0, 1]))
            new_to_old_dict_total[new_node_id] = nodes
            #print(new_to_old_dict_total)
            #print(nodes)
            #print(nodes_array_sub)
            #print('new node id:', new_node_id)
            #print('chr:', chromosome)
            #print('chunk_start:', chunk_start)
            #print('chunk_end:', chunk_end)
        #print('old to new dict:', old_to_new_dict)
        #print('new nodes array:', new_nodes)
        new_nodes = np.vstack(new_nodes)
        old_to_new_dict_total.update(old_to_new_dict)
        nodes_array_copy = np.vstack([nodes_array_copy, new_nodes])
        return nodes_array_copy, old_to_new_dict_total, new_to_old_dict_total
    else:
        return np.empty(shape=(0, 0)), {}, {}


def find_node_set(nodes_array_chr):
    """
    Given a node table and the chromosome number, return a set of node numbers.
    """
    nodes_set = set(nodes_array_chr[:,0])
    return nodes_set


def count_num_inter_chr_nodes(new_nodes, edges_array, new_to_old_dict, old_nodes_set):
    """
    Count number of inter-chromosome nodes for each chromosome.
    """
    num_inter_chr_nodes = 0 # number of inter-chromosome nodes
    new_nodes = np.hstack([new_nodes, np.zeros([new_nodes.shape[0], 1]).astype(int)]) # add a column that indicates whether this node is connected to other chromosomes
    i = 0 # used for indexing of rows
    for new_node in new_nodes: 
        old_nodes = new_to_old_dict[new_node[0]] # map to corresponding old nodes
        try: # if old_nodes is list
            for old_node in old_nodes:
                idx_source = edges_array[:,0]==old_node # find edges that connected to the original node as source
                idx_target = edges_array[:,1]==old_node # find edges that connected to the original node as target
                idx = idx_source | idx_target    
                idx = np.nonzero(idx)[0] # indexes of rows
                old_edges = edges_array[idx] # array of corresponding old nodes 
                old_edges_source = set(old_edges[:,0]) # sources of old edges
                old_edges_target = set(old_edges[:,1]) # targets of old edges
                old_edges_nodes = set.union(old_edges_source, old_edges_target) # set of nodes (old nodes of this chromosome and other nodes connected with them)
                if not old_edges_nodes.issubset(old_nodes_set): # some node is connected to other chromosome
                    num_inter_chr_nodes += 1
                    new_nodes[i, 6] = 1
                    break
        except: # if not a list 
            idx_source = edges_array[:,0]==old_nodes # find edges that connected to the original node as source
            idx_target = edges_array[:,1]==old_nodes # find edges that connected to the original node as target
            idx = idx_source | idx_target    
            idx = np.nonzero(idx)[0] # indexes of rows
            old_edges = edges_array[idx] # array of corresponding old nodes 
            old_edges_source = set(old_edges[:,0]) # sources of old edges
            old_edges_target = set(old_edges[:,1]) # targets of old edges
            old_edges_nodes = set.union(old_edges_source, old_edges_target) # set of nodes (old nodes of this chromosome and other nodes connected with them)
            if not old_edges_nodes.issubset(old_nodes_set): # some node is connected to other chromosome
                num_inter_chr_nodes += 1
                new_nodes[i, 6] = 1
        i += 1 
    assert(num_inter_chr_nodes==np.count_nonzero(new_nodes[:,6]==1))
    return num_inter_chr_nodes, new_nodes


def compute_intra_chr_edges(edges_array, old_nodes_set):
    """
    Return the edges that both ends are inside a single chromosome (intra-chromosome edges of a paticular chromosome).
    
    Arguments:
    edges_array: a numpy array which contains all the edges.
    old_nodes_set: a set of node IDs which belongs to a single chromosome.

    Returns: edge table that contains only intra-chromsome edges
    """
    intra_chr_edges = [row for row in edges_array if row[0] in old_nodes_set and row[1] in old_nodes_set]
    intra_chr_edges = np.vstack(intra_chr_edges)
    return intra_chr_edges


def chr_export_to_gexf(nodes_array, edges_array, reduced_chr_dir, chr, patient_dir):
    """
    Export the reduced chromosome to a gexf file.

    Arguments:
    nodes_array: node table
    edges_array: edge table
    reduced_chr_dir: whre you want to store the output graph
    chr: chromosome number (1-23)
    patient_dir: directory of patient, used to get the code of patient as part of output file name.
    """
    #print(nodes_array)
    #print(edges_array)

    patient_code = patient_dir.split('/')[-1]
    patient_code = patient_code.split('.')[0]
    gexf_path = reduced_chr_dir + 'chr' + str(chr) + '-' + patient_code + '.gexf'
    print('saving reduced chromsome in:', gexf_path)

    reduced_graph = nx.Graph() # initiate empty graph

    '''nodes'''
    node_list = list(nodes_array[:,0]) # node list
    reduced_graph.add_nodes_from(node_list) # add nodes to graph

    '''node attributes'''
    nodes_array_df = pd.DataFrame(data=nodes_array, columns=['node-id', 'chromosome', 'chunk_start', 'chunk_end', 'has_snp', 'new_merged', 'inter_chr'])
    nodes_array_df = nodes_array_df[['node-id', 'chunk_start', 'chunk_end', 'has_snp', 'new_merged', 'inter_chr']]
    nodes_array_df = nodes_array_df.set_index('node-id')
    node_attr = nodes_array_df.to_dict('index') # make node dictionary 
    nx.set_node_attributes(reduced_graph, node_attr) # add node dictionary as node attributes
    
    '''edges'''
    if edges_array is None: # for chromosome 12, it is possible that there is only 1 node after reduction, thus there is no newly merged edges.
        nx.write_gexf(reduced_graph, gexf_path) # export the reduced graph as gexf file.
    else:
        edge_list = list(zip(edges_array[:,0].astype(int), edges_array[:,1].astype(int))) # pairs of source and target as list of tuples
        reduced_graph.add_edges_from(edge_list) # add edges to graph
        nx.write_gexf(reduced_graph, gexf_path) # export the reduced graph as gexf file.
   
    '''
    # edges
    self.edges_reduced['edge_names'] = list(zip(self.edges_reduced.source, self.edges_reduced.target)) # add reduced edge list to reduced edge table
    self.edges_reduced.drop(columns=['source', 'target'], inplace=True)# drop source and target column
    reduced_graph.add_edges_from(list(self.edges_reduced['edge_names'])) # add edges to graph
    self.edges_reduced.set_index('edge_names', inplace=True)# make new edge names index
    edge_attr = self.edges_reduced.to_dict('index') # make dictionary of edge attributes    
    nx.set_edge_attributes(reduced_graph, edge_attr)
    '''


if __name__ == "__main__":
    '''options and input arguments'''
    args = get_args()
    edge_dir = args.edge_dir
    node_dir = args.node_dir
    snps_dir = args.snps_dir
    patient_dir = args.patient_dir
    snp_weight_dir = args.snp_weight_dir
    verbose = int(args.verbose)
    reduced_node_dir = args.reduced_node_dir
    reduced_edge_dir = args.reduced_edge_dir
    reduced_chr_dir = args.reduced_chr_dir
    reduced_graph_statistics = args.reduced_graph_statistics
    chr = int(args.chr)

    np.set_printoptions(threshold=sys.maxsize)

    print('*****************************************************************')
    print('loading the main graph and preprocessing...')
    nodes_array, edges_array, snp_map, node_id_set = load_graph(node_dir, edge_dir, snps_dir)
    
    '''nodes_array: [node-id, chromosome, chunk_start, chunk_end, has_snp]'''
    nodes_array = load_patient(nodes_array, patient_dir, snp_map, node_id_set, snp_weight_dir, snp_weight_th=0.00016)
    print('total number of nodes in main graph: ', nodes_array.shape[0])
    print('total number of SNP nodes in main graph: ', np.count_nonzero(nodes_array[:,4]==1))

    edges_array = filter_edges(edges_array, th=0.05) # filter out unimportant edges
    print('total number of edges in main graph: ', edges_array.shape[0])

    print('-----------------------------------------------------------------') 
    print('merging nodes of chromosome {}...'.format(chr))
    nodes_array_chr = nodes_array[nodes_array[:,1]==chr, :]
    print('number of nodes of chromosome {} before merging: {}'.format(chr, nodes_array_chr.shape[0]))
    print('number of SNP nodes before merging: ', np.count_nonzero(nodes_array_chr[:,4]==1))
    old_nodes_set = find_node_set(nodes_array_chr) # set of original nodes of this chromosome        

    '''new_nodes: [node-id, chromosome, chunk_start, chunk_end, has_snp, new_merged]'''
    new_nodes, old_to_new_dict, new_to_old_dict = merge_chr_nodes(nodes_array_chr)
    '''new_nodes: [node-id, chromosome, chunk_start, chunk_end, has_snp, new_merged, inter_chr]'''    
    num_inter_chr_nodes, new_nodes = count_num_inter_chr_nodes(new_nodes, edges_array, new_to_old_dict, old_nodes_set)
    print('total number of nodes of chromosome {} after merging: {}'.format(chr, new_nodes.shape[0]))
    print('number of SNP nodes after merging: ', np.count_nonzero(new_nodes[:,4]==1))
    print('number of inter chromosome nodes after merging: ', num_inter_chr_nodes)

    print('-----------------------------------------------------------------')    
    print('merging edges of chromosome {}...'.format(chr))

    intra_chr_edges = compute_intra_chr_edges(edges_array, old_nodes_set)
    print('number of intra chromosome edges before merging:', intra_chr_edges.shape[0])

    new_edges = merge_edges(edges_array = intra_chr_edges, old_to_new_dict = old_to_new_dict, num_processes=1)
    if new_edges is None:
        print('number of new edges (intra) after merging:', 0)
    else:
        print('number of new edges (intra) after merging:', new_edges.shape[0])

    chr_export_to_gexf(new_nodes, new_edges, reduced_chr_dir, chr, patient_dir)

    



     




