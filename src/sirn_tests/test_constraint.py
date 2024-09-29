from sirn.constraint import Constraint, ReactionClassification, CompatibilityCollection    # type: ignore
from sirn.named_matrix import NamedMatrix   # type: ignore
from sirn.network import Network  # type: ignore

import itertools
import numpy as np
from scipy.special import factorial  # type: ignore
import unittest


IGNORE_TEST = False
IS_PLOT = False
reactant_arr = np.array([[1, 0], [0, 1], [0, 0]]) # Must have 3 rows to be consistent with DummyConstraint
product_arr = np.array([[0, 1], [1, 0], [0, 0]])
NUM_SPECIES, NUM_REACTION = reactant_arr.shape
SPECIES_NAMES = ["S" + str(i) for i in range(NUM_SPECIES)]
REACTION_NAMES = ["J" + str(i) for i in range(NUM_REACTION)]
REACTANT_NMAT = NamedMatrix(reactant_arr,  row_names=SPECIES_NAMES, column_names=REACTION_NAMES)
PRODUCT_NMAT = NamedMatrix(product_arr,  row_names=SPECIES_NAMES, column_names=REACTION_NAMES)


#############################
class DummyConstraint(Constraint):
    
    def __init__(self, reactant_nmat:NamedMatrix, product_nmat:NamedMatrix):
        super().__init__(reactant_nmat=reactant_nmat, product_nmat=product_nmat)
        #
        self.species_names = ["A", "B", "C"]
        self._categorical_nmat = NamedMatrix(np.array([[0, 1], [1, 0], [1, 1]]),
                row_names=self.species_names, column_names=REACTION_NAMES)
        self._enumerated_nmat = NamedMatrix(np.array([[0, 10], [10, 0], [10, 10]]),
                row_names=self.species_names, column_names=REACTION_NAMES)
        
    def scale(self, scale:int)->'DummyConstraint':
        num_row = scale*len(self.species_names)
        reactant_nmat = NamedMatrix.vstack([self.reactant_nmat]*scale, is_rename=True)
        product_nmat = NamedMatrix.vstack([self.product_nmat]*scale, is_rename=True)
        constraint = DummyConstraint(reactant_nmat, product_nmat)
        equality_arr = np.vstack([self.equality_nmat.values]*scale)
        inequality_arr = np.vstack([self.inequality_nmat.values]*scale)
        constraint._categorical_nmat = NamedMatrix(equality_arr, row_names=np.array(range(num_row)),
                column_names=REACTION_NAMES)
        constraint._enumerated_nmat = NamedMatrix(inequality_arr, row_names=np.array(range(num_row)),
                column_names=REACTION_NAMES)
        return constraint

    @property
    def categorical_nmat(self)->NamedMatrix:
        return self._categorical_nmat
    
    @property
    def enumerated_nmat(self)->NamedMatrix:
        return self._enumerated_nmat

    @classmethod 
    def makeDummyConstraint(cls, num_species:int=3, num_reaction:int=3):
        for _ in range(100):
            network = Network.makeRandomNetworkByReactionType(num_reaction, num_species)
            if (num_species != network.num_species) or (num_reaction != network.num_reaction):
                continue
            break
        else:
            raise RuntimeError("Failed to make a random network")
        return DummyConstraint(network.reactant_nmat, network.product_nmat)


#############################
class ScalableDummyConstraint(Constraint):
    
    def __init__(self, reference_size):
        reactant_nmat = NamedMatrix(np.array(np.random.randint(0, 2, (reference_size, reference_size))))
        product_nmat = NamedMatrix(np.array(np.random.randint(0, 2, (reference_size, reference_size))))
        super().__init__(reactant_nmat=reactant_nmat, product_nmat=product_nmat)
        #
        self.num_species = len(reactant_nmat.row_names)
        num_column = 5
        self._categorical_nmat = NamedMatrix(np.array(np.random.randint(0, 2, (self.num_species, num_column))))
        self._enumerated_nmat = NamedMatrix(np.array(np.random.randint(0, 2, (self.num_species, num_column))))
        
    def scale(self, scale:int)->'ScalableDummyConstraint':
        reactant_nmat = NamedMatrix.vstack([self.reactant_nmat]*scale, is_rename=True)
        product_nmat = NamedMatrix.vstack([self.product_nmat]*scale, is_rename=True)
        constraint = DummyConstraint(reactant_nmat, product_nmat)
        equality_arr = np.vstack([self.equality_nmat.values]*scale)
        inequality_arr = np.vstack([self.inequality_nmat.values]*scale)
        constraint._categorical_nmat = NamedMatrix(equality_arr, row_names=np.array(range(self.num_row)))
        constraint._enumerated_nmat = NamedMatrix(inequality_arr, row_names=np.array(range(self.num_row)))
        return constraint

    @property
    def categorical_nmat(self)->NamedMatrix:
        return self._categorical_nmat
    
    @property
    def enumerated_nmat(self)->NamedMatrix:
        return self._enumerated_nmat


#############################
class TestReactionClassification(unittest.TestCase):

    def setUp(self):
        self.reaction_classification = ReactionClassification(num_reactant=1, num_product=2)
    
    def testConstructor(self):
        if IGNORE_TEST:
            return
        self.assertEqual(str(self.reaction_classification), "uni-bi")

    def testMany(self):
        if IGNORE_TEST:
            return
        iter =  itertools.product(range(4), repeat=2)
        for num_reactant, num_product in iter:
            reaction_classification = ReactionClassification(num_reactant=num_reactant,
                  num_product=num_product)
            if (num_reactant == 0) or (num_product == 0):
                self.assertTrue("null" in str(reaction_classification))
            if (num_reactant == 1) or (num_product == 1):
                self.assertTrue("uni" in str(reaction_classification))
            if (num_reactant == 2) or (num_product == 2):
                self.assertTrue("bi" in str(reaction_classification))
            if (num_reactant == 3) or (num_product == 3):
                self.assertTrue("multi" in str(reaction_classification))


#############################
class TestCompatibilityCollection(unittest.TestCase):

    def setUp(self) -> None:
        self.collection = CompatibilityCollection(2, 3)

    def testNumPermutation(self):
        if IGNORE_TEST:
            return
        for size in np.random.randint(2, 50, 1000):
            collection = CompatibilityCollection(size, size)
            [collection.add(i-1, range(i)) for i in range(1, size+1)]
            self.assertTrue(np.isclose(collection.log10_num_permutation, np.log10(factorial(size))))

    def testPrune(self):
        if IGNORE_TEST:
            return
        max_permutation = 1000
        for size in np.random.randint(5, 20, 100):
            collection = CompatibilityCollection(size, size)
            [collection.add(i-1, range(i)) for i in range(1, size+1)]
            new_collection = collection.prune(max_permutation)
            self.assertTrue(new_collection.log10_num_permutation <= max_permutation)


#############################
class TestConstraint(unittest.TestCase):

    def setUp(self):
        self.constraint = DummyConstraint(reactant_nmat=REACTANT_NMAT, product_nmat=PRODUCT_NMAT)

    def testConstructor(self):
        if IGNORE_TEST:
            return
        self.assertEqual(REACTANT_NMAT, self.constraint.reactant_nmat)
        self.assertEqual(PRODUCT_NMAT, self.constraint.product_nmat)

    def testCopyEqual(self):
        if IGNORE_TEST:
            return
        constraint = self.constraint.copy()
        self.assertTrue(self.constraint == constraint.copy())
        #
        self.constraint.reactant_nmat.values[0,0] = 100
        self.assertFalse(self.constraint == constraint.copy())

    def testSerializeDeserialize(self):
        if IGNORE_TEST:
            return
        serialization_str = self.constraint.serialize()
        constraint = DummyConstraint.deserialize(serialization_str)
        self.assertEqual(self.constraint, constraint)
    
    def testClassifyReactions(self):
        if IGNORE_TEST:
            return
        reaction_classifications = self.constraint.classifyReactions()
        self.assertTrue(all([isinstance(rc, ReactionClassification) for rc in reaction_classifications]))

    def testCalculateCompatibility(self):
        if IGNORE_TEST:
            return
        result = self.constraint.calculateBooleanCompatibilityVector(self.constraint.equality_nmat,
              self.constraint.equality_nmat, is_equality=True)
        num_true = np.sum(result)
        self.assertEqual(num_true, self.constraint.equality_nmat.num_row)
        #
        result = self.constraint.calculateBooleanCompatibilityVector(self.constraint.inequality_nmat,
              self.constraint.equality_nmat, is_equality=True)
        num_true = np.sum(result)
        self.assertEqual(num_true, 0)
        #
        result = self.constraint.calculateBooleanCompatibilityVector(self.constraint.equality_nmat,
              self.constraint.inequality_nmat, is_equality=False)
        num_true = np.sum(result)
        self.assertEqual(num_true, 5)

    def testMakeCompatibilityCollection(self):
        if IGNORE_TEST:
            return
        compatibility_collection = self.constraint.makeCompatibilityCollection(self.constraint)
        self.assertTrue(np.isclose(compatibility_collection.log10_num_permutation, 0))
    
    def testMakeCompatibilityCollectionScale(self):
        if IGNORE_TEST:
            return
        scale = 5000  # scaling factor
        constraint = ScalableDummyConstraint(50)
        new_constraint = constraint.scale(scale)
        compatibility_collection = constraint.makeCompatibilityCollection(new_constraint)
        trues = [len(lst) >= scale
                   for lst in compatibility_collection.compatibilities]
        self.assertTrue(all(trues))

    def testCalculateLog10UnconstrainedPermutation(self):
        if IGNORE_TEST:
            return
        for size in range(3, 20):
            log10_permutation = self.constraint.calculateLog10UnconstrainedPermutation(size, size)
            self.assertTrue(np.isclose(log10_permutation, 2*np.log10(factorial(size))))



if __name__ == '__main__':
    unittest.main()