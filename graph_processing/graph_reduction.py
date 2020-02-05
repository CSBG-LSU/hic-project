"""
Reduce the size of the graph by contracting edges.
"""
import argparse
from hic_graph import HicGraph

def get_args():
    parser = argparse.ArgumentParser('python')

    parser.add_argument('-edge_dir',
                        #default='../../test_data/G_snps_23_edge.h5',
                        default='../../test_data/test.h5',
                        required=False,
                        help='directory of output edge file.')  

    parser.add_argument('-node_dir',
                        #default='../../test_data/G_snps_23_node.csv',
                        default='../../test_data/test.csv',
                        required=False,
                        help='directory of output edge file.')  

    parser.add_argument('-snps_dir',
                        default='../../final_results_5kb_to_Dl/snps_splitted_chr_final/',
                        required=False,
                        help='directory of output edge file.') 
                 
    return parser.parse_args()


if __name__ == "__main__":
    args = get_args()
    edge_dir = args.edge_dir
    node_dir = args.node_dir
    snps_dir = args.snps_dir
    hic_graph = HicGraph(edge_dir, node_dir, snps_dir)
    hic_graph.load_graph()
    hic_graph.load_snps()



