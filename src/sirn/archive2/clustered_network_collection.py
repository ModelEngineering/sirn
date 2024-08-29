'''A container for collections of structurally identical networks and their statistics.'''
"""
Has a string representation and can construct from its string representation.
"""


from sirn import constants as cn # type: ignore
from sirn.clustered_network import ClusteredNetwork  # type: ignore

import collections
import numpy as np
import pandas as pd  # type: ignore
from typing import List, Optional

Repr = collections.namedtuple('Repr',
     ['is_structural_identity_strong', 'hash_val', 'clustered_networks'])


class ClusteredNetworkCollection(object):
    # Collection of networks that are structurally identical

    def __init__(self, clustered_networks:List[ClusteredNetwork],
                 is_structural_identity_strong:bool=True, hash_val:int=-1,
                 antimony_dir:Optional[str]=None):
        self.clustered_networks = clustered_networks  # type: ignore
        self.is_structural_identity_strong = is_structural_identity_strong
        self.hash_val = hash_val
        self.directory = antimony_dir # Directory where the network is stored

    def copy(self)->'ClusteredNetworkCollection':
        return ClusteredNetworkCollection([cn.copy() for cn in self.clustered_networks],
                is_structural_identity_strong=self.is_structural_identity_strong,
                hash_val=self.hash_val)

    def __eq__(self, other:object)->bool:
        if not isinstance(other, ClusteredNetworkCollection):
            return False
        return all([n1 == n2 for n1, n2 in zip(self.clustered_networks, other.clustered_networks)]) and \
                (self.is_structural_identity_strong == other.is_structural_identity_strong) and \
                (self.hash_val == other.hash_val)
    
    def isSubset(self, other:object)->bool:
        # Is this a subset of other?
        if not isinstance(other, ClusteredNetworkCollection):
            return False
        for this_network in self.clustered_networks:
            is_found = False
            for other_network in other.clustered_networks:
                if this_network == other_network:
                    is_found = True
                    break
            if not is_found:
                return False
        return True

    def __len__(self)->int:
        return len(self.clustered_networks)
    
    def __repr__(self)->str:
        # String encoding sufficient to reconstruct the object
        if self.is_structural_identity_strong:
            prefix = cn.IDENTITY_PREFIX_STRONG
        else:
            prefix = cn.IDENTITY_PREFIX_WEAK
        reprs = [cn.__repr__() for cn in self.clustered_networks]   
        clustered_networks_str = cn.NETWORK_NAME_DELIMITER.join(reprs)
        result = f"{self.hash_val}{prefix}{clustered_networks_str}"
        return result

    @staticmethod 
    def parseRepr(repr_str:str)->Repr:
        """
        Parses a string representation of a ClusteredNetworkCollection.

        Args:
            repr_str (str): _description_

        Returns:
            str
        """
        # Find the hash_val
        positions = np.array([-1, -1])
        for idx, stg in enumerate([cn.IDENTITY_PREFIX_STRONG, cn.IDENTITY_PREFIX_WEAK]):
            positions[idx] = repr_str.find(stg)
        pos = np.min([p for p in positions if p != -1])
        hash_val = int(repr_str[:pos])
        is_structural_identity_strong = repr_str[pos] == cn.IDENTITY_PREFIX_STRONG 
        # Find the ClasteredNetwork.repr
        reprs = repr_str[pos+1:].split(cn.NETWORK_NAME_DELIMITER)
        clustered_networks = [ClusteredNetwork.makeFromRepr(repr) for repr in reprs]
        return Repr(is_structural_identity_strong=is_structural_identity_strong,
                hash_val=hash_val, clustered_networks=clustered_networks)

    @classmethod 
    def makeFromRepr(cls, repr_str:str)->'ClusteredNetworkCollection':
        """
        Constructs a ClusteredNetworkCollection from a string representation

        Args:
            repr_str (str): _description_

        Returns:
            ClusteredNetworkCollection: _description_
        """
        repr = cls.parseRepr(repr_str)
        return ClusteredNetworkCollection(repr.clustered_networks,
                is_structural_identity_strong=repr.is_structural_identity_strong,
                hash_val=repr.hash_val)
    
    def add(self, clustered_network:ClusteredNetwork):
        self.clustered_networks.append(clustered_network)