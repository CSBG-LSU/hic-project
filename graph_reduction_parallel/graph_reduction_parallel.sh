#!/bin/bash
#PBS -q workq
#PBS -l nodes=1:ppn=20
#PBS -l walltime=12:00:00
#PBS -N graph_redu_516
#PBS -A hpc_michal01
#PBS -j oe

module purge
source activate graph
cd /work/derick/hi-c/hic-project/graph_reduction_parallel/
python graph_reduction_parallel.py -edge_dir ../../processed_main_graph/final_edge.h5 -node_dir ../../processed_main_graph/final_node.csv > ./log/graph_reduction_1proc.log 2>&1










