from sirn.constraint import NULL_NMAT  # type: ignore
from sirn.species_constraint import SpeciesConstraint # type: ignore
from sirn.named_matrix import NamedMatrix # type: ignore
from sirn.network import Network # type: ignore

import numpy as np
import re
import time
import unittest


IGNORE_TEST = False
IS_PLOT = False
REACTANT_MATRIX = NamedMatrix(np.array([[1, 0], [0, 1], [0, 0]]))
PRODUCT_MATRIX = NamedMatrix(np.array([[1, 1], [1, 0], [0, 0]]))
NUM_ITERATION = 10


#############################
# Tests
#############################
class TestSpeciesConstraint(unittest.TestCase):

    def setUp(self):
        self.constraint = SpeciesConstraint(REACTANT_MATRIX.copy(), PRODUCT_MATRIX.copy()) 

    def testConstructor(self):
        if IGNORE_TEST:
            return
        self.assertEqual(self.constraint.reactant_nmat, REACTANT_MATRIX)
        self.assertEqual(self.constraint.product_nmat, PRODUCT_MATRIX)
        self.assertEqual(self.constraint._categorical_nmat, NULL_NMAT)
        self.assertEqual(self.constraint._numerical_enumerated_nmat, NULL_NMAT)

    def testMakeSpeciesConstraintMatrixScale(self):
        if IGNORE_TEST:
            return
        for _ in range(10):
            size = 20
            network = Network.makeRandomNetworkByReactionType(size, size)
            uni_result =  re.findall(": S. ->", str(network))
            num_uni_re = len(list(uni_result))
            uni_result =  re.findall(": S.. ->", str(network))
            num_uni_re += len(list(uni_result))
            species_constraint = SpeciesConstraint(network.reactant_nmat, network.product_nmat)
            named_matrix = species_constraint._makeReactantProductConstraintMatrix()
            self.assertTrue(isinstance(named_matrix, NamedMatrix))
            df = named_matrix.dataframe
            uni_names = ['r_uni-null', 'r_uni-uni', 'r_uni-bi', 'r_uni-multi']
            num_uni_nmat = df[uni_names].sum().sum()
            self.assertEqual(num_uni_re, num_uni_nmat)

    def testMakeAutocatalysisConstraint(self):
        if IGNORE_TEST:
            return
        for _ in range(30):
            size = 20
            network = Network.makeRandomNetworkByReactionType(size, size)
            collection = []
            for stg in [" ", "\n", "$"]:
                totals = [len(re.findall("S" + str(n) + " .*->.*S" + str(n) + stg, str(network)))
                      for n in range(size)]
                collection.append(totals)
            total_arr = np.sign(np.sum(np.array(collection), axis=0))
            species_constraint = SpeciesConstraint(network.reactant_nmat, network.product_nmat)
            named_matrix = species_constraint._makeAutocatalysisConstraint()
            self.assertEqual(np.sum(total_arr), np.sum(named_matrix.values))

    def testSpeciesConstraintMatrix(self):
        if IGNORE_TEST:
            return
        for _ in range(30):
            size = 20
            network = Network.makeRandomNetworkByReactionType(size, size)
            species_constraint = SpeciesConstraint(network.reactant_nmat, network.product_nmat)
            named_matrix = species_constraint._makeAutocatalysisConstraint()
            self.assertTrue(isinstance(named_matrix, NamedMatrix))
            df = named_matrix.dataframe
            self.assertGreater(len(df), 0)

    def testCategoricalAndEnumeratedConstraints(self):
        if IGNORE_TEST:
            return
        for _ in range(4):
            self.constraint.setSubset(True)
            self.assertTrue(self.constraint.equality_nmat is NULL_NMAT)
            self.assertTrue(self.constraint.numerical_inequality_nmat is not NULL_NMAT)
            #
            self.constraint.setSubset(False)
            self.assertTrue(self.constraint.equality_nmat is not NULL_NMAT)
            self.assertTrue(self.constraint.numerical_inequality_nmat is NULL_NMAT)

    def testmakeCompatibilityCollection(self):
        if IGNORE_TEST:
            return
        num_permutations = []
        for _ in range(100):
            reference_size = 15
            filler_size = 5*reference_size
            network = Network.makeRandomNetworkByReactionType(reference_size, reference_size)
            big_network = network.fill(num_fill_reaction=filler_size, num_fill_species=filler_size)
            reaction_constraint = SpeciesConstraint(network.reactant_nmat, network.product_nmat,
                                                   is_subset=True)
            big_reaction_constraint = SpeciesConstraint(big_network.reactant_nmat, big_network.product_nmat,
                                                       is_subset=True)
            compatibility_collection = reaction_constraint.makeCompatibilityCollection(
                  big_reaction_constraint)
            name_arr = np.array(big_reaction_constraint.reactant_nmat.row_names)
            for i, arr in enumerate(compatibility_collection.compatibilities):
                reference_name = "S" + str(i)
                target_names = [name_arr[i] for i in arr]
                self.assertTrue(reference_name in target_names)
            num_permutations.append(compatibility_collection.log10_num_permutation)
        #print(np.mean(num_permutations))

    def testMakeBitwiseReactantProductConstraintMatrix(self):
        if IGNORE_TEST:
            return
        for _ in range(NUM_ITERATION):
            size = 10
            network = Network.makeRandomNetworkByReactionType(size, size)
            species_constraint = SpeciesConstraint(network.reactant_nmat, network.product_nmat)
            named_matrix = species_constraint._makeBitwiseReactantProductConstraintMatrix()
            self.assertTrue(isinstance(named_matrix, NamedMatrix))
            df = named_matrix.dataframe
            self.assertGreater(len(df), 0)

    def testMakeReactantProductCountConstraintMatrix(self):
        if IGNORE_TEST:
            return
        for _ in range(NUM_ITERATION):
            size = 10
            network = Network.makeRandomNetworkByReactionType(size, size)
            species_constraint = SpeciesConstraint(network.reactant_nmat, network.product_nmat)
            named_matrix = species_constraint._makeReactantProductCountConstraintMatrix()
            count_arr = np.sum(named_matrix.values, axis=1)
            for idx in range(len(count_arr)):
                scanned_count = str(network).count("S" + str(idx))
                self.assertEqual(count_arr[idx], scanned_count)
            df = named_matrix.dataframe
            self.assertGreater(len(df), 0)


if __name__ == '__main__':
    unittest.main()