import unittest

import sys, os
# For Python 3, use the translated version of the library.
# For Python 2, find the library one directory up.
if sys.version < '3':
    sys.path.append(os.path.dirname(sys.path[0]))
import febabel as f


class TestFEproblem(unittest.TestCase):


    def test_descendants(self):
        p = f.problem.FEproblem()
        matl1 = f.materials.Ogden([1,2,3,4,5,6,7],[8,9,10,11,12,13,14], 2.2)
        matl2 = f.materials.TransIsoElastic(15,16,17,18,
            axis=f.materials.SphericalOrientation((0,0,0),(0,0,1)),
            base=f.materials.VerondaWestmann(19,20,21),
        )
        Node = f.geometry.Node
        nodes = [
            Node((0,0,0)), Node((1,0,0)), Node((1,1,0)), Node((0,1,0)),
            Node((0,0,1)), Node((1,0,1)), Node((1,1,1)), Node((0,1,1)),
            Node((0,0,2)), Node((1,0,2)), Node((1,1,2)), Node((0,1,2)),
        ]
        p.sets[''] = set((
            f.geometry.Hex8(nodes[0:8], matl1),
            f.geometry.Hex8(nodes[4:12], matl2) ))

        desc = p.get_descendants()
        # 2 Elements, 12 Nodes, 3 Materials (1 base), 1 AxisOrientation.
        self.assertEqual(len(desc), 2 + 12 + 3 + 1)




if __name__ == '__main__':
    unittest.main()
