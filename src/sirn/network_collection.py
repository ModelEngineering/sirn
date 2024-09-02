'''Container of networks. Can serialize and deserialize to a DataFrame. Construct from Antimony files. '''


from sirn import constants as cn   # type: ignore
from src.sirn.network import Network   # type: ignore

import collections
import copy
import os
import pandas as pd # type: ignore
import numpy as np
from typing import List, Optional, Dict


ANTIMONY_EXTS = [".ant", ".txt", ""]  # Antimony file extensions


ArrayContext = collections.namedtuple('ArrayContext', "string, num_row, num_column")


####################################
class NetworkCollection(object):
        
    def __init__(self, networks: List[Network], directory:Optional[str]=None)->None:
        """
        Args:
            networks (List[Network]): Networks in the collection
        """
        self.networks = networks
        self.network_dct = {n.network_name: n for n in networks}
        self.directory = directory

    def add(self, network:Network)->None:
        self.networks.append(network)

    def __eq__(self, other:'NetworkCollection')->bool:  # type: ignore
        # Check that collections have networks with the same attribute values
        if len(self) != len(other):
            return False
        # Check the network names
        network1_dct = {n.network_name: n for n in self.networks}
        network2_dct = {n.network_name: n for n in other.networks}
        key_set = set(network1_dct.keys())
        key_diff = key_set.symmetric_difference(set(network2_dct.keys()))
        if len(key_diff) > 0:
            return False
        #
        for key in key_set:
            if not network1_dct[key] == network2_dct[key]:
                return False
        return True

    def __len__(self)->int:
        return len(self.networks)
    
    def __repr__(self)->str:
        names = [n.network_name for n in self.networks]
        return "---".join(names)
    
    def _findCommonType(self, collection_identity_type1:str, collection_identity_type2:str)->str:
        if (collection_identity_type1 == cn.STRUCTURAL_IDENTITY_TYPE_NOT) \
                or (collection_identity_type2 == cn.STRUCTURAL_IDENTITY_TYPE_NOT):
            return cn.STRUCTURAL_IDENTITY_TYPE_NOT
        if (collection_identity_type1 == cn.STRUCTURAL_IDENTITY_TYPE_WEAK) \
                or (collection_identity_type2 == cn.STRUCTURAL_IDENTITY_TYPE_WEAK):
            return cn.STRUCTURAL_IDENTITY_TYPE_WEAK
        return cn.STRUCTURAL_IDENTITY_TYPE_STRONG
    
    def __add__(self, other:'NetworkCollection')->'NetworkCollection':
        """
        Union of two network collections. Constructs the correct collection_identity_type.

        Args:
            other (NetworkCollection)

        Returns:
            NetworkCollection: _description_

        Raises:
            ValueError: Common names between collections
        """
        # Error checking
        this_names = set([n.network_name for n in self.networks])
        other_names = set([n.network_name for n in other.networks]) 
        common_names = this_names.intersection(other_names)
        if len(common_names) > 0:
            raise ValueError(f"Common names between collections: {common_names}")
        # Construct the new collection
        networks = copy.deepcopy(self.networks)
        networks.extend(other.networks)
        directory = None
        if self.directory == other.directory:
            directory = self.directory
        return NetworkCollection(networks, directory=directory)
    
    def copy(self)->'NetworkCollection':
        return copy.deepcopy(self)
    
    @classmethod
    def makeRandomCollection(cls, num_species:int=3, num_reaction:int=3, num_network:int=10)->'NetworkCollection':
        """
        Make a collection of random networks according to the specified parameters.

        Args:
            array_size (int, optional): Size of the square matrix
            num_network (int, optional): Number of networks

        Returns:
            NetworkCollection
        """
        networks = [Network.makeRandomNetworkByReactionType(num_species=num_species, num_reaction=num_reaction)
                    for _ in range(num_network)]
        return cls(networks)

    @classmethod
    def makeFromAntimonyDirectory(cls, indir_path:str, max_file:Optional[int]=None,
                processed_network_names:Optional[List[str]]=None,
                report_interval:Optional[int]=None)->'NetworkCollection':
        """Creates a NetworkCollection from a directory of Antimony files.

        Args:
            indir_path (str): Path to the antimony model directory
            max_file (int): Maximum number of files to process
            processed_network_names (List[str]): Names of models already processed
            report_interval (int): Report interval

        Returns:
            NetworkCollection
        """
        ffiles = os.listdir(indir_path)
        networks = []
        network_names = []
        if processed_network_names is not None:
            network_names = list(processed_network_names)
        for count, ffile in enumerate(ffiles):
            if report_interval is not None and count % report_interval == 0:
                is_report = True
            else:
                is_report = False
            network_name = ffile.split('.')[0]
            if network_name in network_names:
                if is_report:
                    print(".", end='')
                continue
            if (max_file is not None) and (count >= max_file):
                break
            if not any([ffile.endswith(ext) for ext in ANTIMONY_EXTS]):
                continue
            path = os.path.join(indir_path, ffile)
            network = Network.makeFromAntimonyFile(path, network_name=network_name)
            networks.append(network)
            if is_report:
                print(f"Processed {count} files.")
        return NetworkCollection(networks, directory=indir_path)

    def serialize(self)->pd.DataFrame:
        """Constructs a DataFrame from a NetworkCollection

        Returns:
            pd.DataFrame: See SERIALIZATION_NAMES
               DataFrame.metadata: Dictionary of metadata
                    "directory": Directory of the Antimony files
        """
        sers = [n.serialize() for n in self.networks]
        return pd.concat(sers, axis=1).transpose()

    @classmethod 
    def deserialize(cls, df:pd.DataFrame)->'NetworkCollection':
        """Deserializes a DataFrame to a NetworkCollection

        Args:
            df: pd.DataFrame

        Returns:
            NetworkCollection
        """
        networks = []
        for _, row in df.iterrows():
            network = Network.deserialize(row)
            networks.append(network)
        return NetworkCollection(networks)