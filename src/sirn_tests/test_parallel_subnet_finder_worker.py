import sirn.constants as cn  # type: ignore
import sirn.parallel_subnet_finder_worker as psfw  # type: ignore
from sirn.network import Network  # type: ignore
from sirn.mock_queue import MockQueue  # type: ignore
from sirn.model_serializer import ModelSerializer  # type: ignore

import json
import os
import pandas as pd # type: ignore
import numpy as np
from typing import Tuple
import unittest

IGNORE_TEST = False
IS_PLOT =  False
SIZE = 10
NUM_NETWORK = 10    
BASE_CHECKPOINT_PATH = os.path.join(cn.TEST_DIR, "test_subnet_finder_checkpoint.csv")
TASK0_CHECKPOINT_PATH = psfw.WorkerCheckpointManager.makeTaskPath(BASE_CHECKPOINT_PATH, 0)
TASK1_CHECKPOINT_PATH = psfw.WorkerCheckpointManager.makeTaskPath(BASE_CHECKPOINT_PATH, 1)
REFERENCE_SERIALIZER_PATH = os.path.join(cn.TEST_DIR, "test_reference_networks.csv")
TARGET_SERIALIZER_PATH = os.path.join(cn.TEST_DIR, "test_target_networks.csv")
REMOVE_FILES:list = [BASE_CHECKPOINT_PATH, TASK0_CHECKPOINT_PATH, TASK1_CHECKPOINT_PATH,
      REFERENCE_SERIALIZER_PATH, TARGET_SERIALIZER_PATH]
REFERENCE_NETWORKS = [Network.makeRandomNetworkByReactionType(SIZE, is_prune_species=True)
      for _ in range(NUM_NETWORK)]
TARGET_NETWORKS = [n.fill(num_fill_reaction=SIZE, num_fill_species=SIZE) for n in REFERENCE_NETWORKS]


#############################
# Tests
#############################
def makeDataframe(num_network:int)->pd.DataFrame:
    # Creates a dataframe used by the WorkerCheckpointManager
    reference_networks = [Network.makeRandomNetworkByReactionType(3, is_prune_species=True) for _ in range(num_network)]
    target_networks = [Network.makeRandomNetworkByReactionType(3, is_prune_species=True) for _ in range(num_network)]
    dct = {cn.FINDER_REFERENCE_NETWORK: [str(n) for n in range(num_network)],
           cn.FINDER_INDUCED_NETWORK: [str(n) for n in range(num_network, 2*num_network)]}
    df = pd.DataFrame(dct)
    df[cn.FINDER_REFERENCE_NAME] = [str(n) for n in reference_networks]
    df[cn.FINDER_TARGET_NAME] = [str(n) for n in target_networks]
    df[cn.FINDER_NAME_DCT] = [json.dumps(dict(a=n)) for n in range(num_network)]
    return df


#############################
class TestParallelSubnetFinderWorker(unittest.TestCase):

    def setUp(self):
        self.remove()
        self.queue = MockQueue()
        self.queue.put(psfw.Workunit(is_done=True))

    def tearDown(self):
        self.remove()

    def remove(self):
        for ffile in REMOVE_FILES:
            if os.path.exists(ffile):
                os.remove(ffile)

    def testExecuteTask(self):
        if IGNORE_TEST:
            return
        #####
        def test(task_idx:int=0, is_initialize:bool=True, num_queue:int=10,
                 num_network:int=NUM_NETWORK, total_task:int=2)->Tuple[pd.DataFrame, pd.DataFrame]:
            # Creates reference and target networks to assess processing by tasks.
            # Returns the full dataframe and the pruned dataframes
            reference_networks = [Network.makeRandomNetworkByReactionType(SIZE, is_prune_species=True)
                  for _ in range(num_network)]
            target_networks = [n.fill(num_fill_reaction=SIZE, num_fill_species=SIZE) for n in reference_networks]
            ModelSerializer.serializerFromNetworks(reference_networks, REFERENCE_SERIALIZER_PATH,
                  is_initialize=True)
            ModelSerializer.serializerFromNetworks(target_networks, TARGET_SERIALIZER_PATH,
                  is_initialize=True)
            queue = MockQueue()
            queue.put(psfw.Workunit(is_done=True))
            psfw.Workunit.addMultipleWorkunits(queue, reference_idxs=range(num_queue))
            full_df = psfw.executeTask(task_idx, queue, total_task, BASE_CHECKPOINT_PATH,
                REFERENCE_SERIALIZER_PATH, TARGET_SERIALIZER_PATH, identity=cn.ID_STRONG,
                is_report=IS_PLOT, is_initialize=is_initialize)
            prune_df, _ = psfw.WorkerCheckpointManager.prune(full_df)
            return full_df, prune_df
        #####
        # Finds the subnets for a single task
        full_df, prune_df = test(task_idx=0, is_initialize=True, num_queue=NUM_NETWORK)
        self.assertEqual(len(full_df), NUM_NETWORK**2)
        self.assertEqual(len(prune_df), len(REFERENCE_NETWORKS))
        checkpoint_df = pd.read_csv(TASK0_CHECKPOINT_PATH)
        self.assertEqual(len(checkpoint_df), NUM_NETWORK**2)
        # Finds all subnets if there is an existing checkpoint
        full_df, prune_df = test(task_idx=0, is_initialize=False, num_queue=NUM_NETWORK)
        self.assertEqual(len(full_df), 2*NUM_NETWORK**2)
        checkpoint_df = pd.read_csv(TASK0_CHECKPOINT_PATH)
        self.assertEqual(len(checkpoint_df), 2*NUM_NETWORK**2)
        # Handle two tasks
        full_df, prune_df = test(task_idx=1, is_initialize=False, num_queue=NUM_NETWORK)
        self.assertEqual(len(full_df), NUM_NETWORK**2)
        dff = pd.read_csv(BASE_CHECKPOINT_PATH)
        self.assertEqual(len(dff), 3*NUM_NETWORK**2)


if __name__ == '__main__':
    unittest.main(failfast=False)