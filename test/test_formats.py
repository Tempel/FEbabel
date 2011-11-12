#!/usr/bin/env python2
from __future__ import with_statement

import unittest, xml.etree.ElementTree as etree

import sys, os
# For Python 3, use the translated version of the library.
# For Python 2, find the library one directory up.
if sys.version > '3':
    from io import BytesIO as StringIO
else:
    try: from cStringIO import StringIO
    except: from StringIO import StringIO
    sys.path.append(os.path.dirname(sys.path[0]))
datadir = os.path.join(os.path.dirname(__file__), 'data')

import febabel as f


class TestFeb(unittest.TestCase):
    # TODO: Test shell elements and their ElementData.


    def test_write_feb(self):
        p = f.problem.FEproblem()
        Node = f.geometry.Node
        matl1 = f.materials.Ogden([1,2,3,4,5,6,7],[8,9,10,11,12,13,14], 2.2)
        matl2 = f.materials.TransIsoElastic(15,16,17,18,
            axis_func=f.materials.SphericalOrientation((0,0,0),(0,0,1)),
            base=f.materials.VerondaWestmann(19,20,21),
        )
        nodes = [
            Node((0,0,0)), Node((1,0,0)), Node((1,1,0)), Node((0,1,0)),
            Node((0,0,1)), Node((1,0,1)), Node((1,1,1)), Node((0,1,1)),
            Node((0,0,2)), Node((1,0,2)), Node((1,1,2)), Node((0,1,2)),
        ]
        p.elements.add(f.geometry.Hex8(nodes[0:8], matl1))
        p.elements.add(f.geometry.Hex8(nodes[4:12], matl2))

        outfile = StringIO()
        p.write_feb(outfile)

        # Check the resulting XML.
        tree = etree.fromstring(outfile.getvalue())

        matls = tree.find('Material').findall('material')
        self.assertEqual(len(matls), 2)
        # Materials are properly numbered.
        self.assertEqual([m.get('id') for m in matls], ['1','2'])
        # Can't assure material order, so find each and check values.
        ogden, trans = (matls[0],matls[1]) if (
            matls[0].get('type') == 'Ogden' ) else (matls[1],matls[0])
        self.assertEqual(ogden.get('type'), 'Ogden')
        self.assertEqual(ogden.find('c1').text, '1')
        self.assertEqual(ogden.find('m3').text, '10')
        self.assertEqual(ogden.find('c6').text, '6')
        self.assertEqual(ogden.find('c7'), None)
        self.assertEqual(ogden.find('m7'), None)
        self.assertEqual(ogden.find('k').text, '2.2')
        self.assertEqual(trans.get('type'), 'trans iso Veronda-Westmann')
        self.assertEqual(trans.find('c1').text, '19')
        self.assertEqual(trans.find('c2').text, '20')
        self.assertEqual(trans.find('c3').text, '15')
        self.assertEqual(trans.find('c4').text, '16')
        self.assertEqual(trans.find('c5').text, '17')
        self.assertEqual(trans.find('k').text, '21')
        self.assertEqual(trans.find('lam_max').text, '18')
        self.assertEqual(trans.find('fiber').get('type'), 'spherical')
        self.assertEqual(trans.find('fiber').text, '0,0,0')

        nodes = tree.find('Geometry').find('Nodes').findall('node')
        self.assertEqual(len(nodes), 12)
        # All nodes are properly numbered.
        self.assertEqual([n.get('id') for n in nodes],
            [str(i) for i in range(1,13)])

        elements = tree.find('Geometry').find('Elements').findall('hex8')
        self.assertEqual(len(elements), 2)
        self.assertEqual([e.get('id') for e in elements], ['1','2'])
        # The two elements share four nodes (but element order can't be assured).
        e0 = elements[0].text.split(',')
        e1 = elements[1].text.split(',')
        self.assertTrue(e0[4:8] == e1[0:4] or e1[4:8] == e0[0:4])
        # Each element is assigned one of the materials.
        e0 = elements[0].get('mat')
        e1 = elements[1].get('mat')
        self.assertTrue( (e0=='1' and e1=='2') or (e1=='1' and e0=='2') )


    def test_write_feb_materials(self):
        p = f.problem.FEproblem()
        nodes = list(map( f.geometry.Node, [(0,0,0), (1,0,0), (0,1,0), (0,0,1)] ))
        mat = f.materials
        materials = [
            mat.NeoHookean(1,2),
            mat.MooneyRivlin(3,4,5),
            mat.Ogden([5,6,7], [8,9,10], 11),
            mat.Rigid((13,14,15)),
            mat.TransIsoElastic(16,17,18,19, mat.NodalOrientation((0,1),(0,3)),
                mat.MooneyRivlin(20,21,22)),
            mat.LinearOrthotropic(23,24,25,26,27,28,29,30,31,
                mat.NodalOrientation((0,2),(2,3))),
            mat.FungOrthotropic(32,33,34,35,36,37,38,39,40,41,42,
                mat.VectorOrientation((0,0,1),(1,0,1))),
            mat.TransIsoElastic(43,44,45,46,
                lambda e: (e.get_vertex_avg(), [0,1,0], [0,0,1]),
                mat.VerondaWestmann(47,48,49)),
        ]
        p.elements.update(f.geometry.Tet4(nodes, m) for m in materials)

        outfile = StringIO()
        p.write_feb(outfile)

        # Check the resulting XML.
        tree = etree.fromstring(outfile.getvalue())
        e_matls = tree.find('Material').findall('material')

        # All ID numbers are assigned in order
        self.assertEqual( [m.get('id') for m in e_matls],
            list(map(str,range(1,len(materials)+1))) )

        # Can't assure order of materials, so make dictionary by type ID.
        matls = dict( (m.get('type'), m) for m in e_matls )

        # Check values for each material.
        nh = matls['neo-Hookean']
        self.assertEqual(nh.find('E').text, '1')
        self.assertEqual(nh.find('v').text, '2')
        mr = matls['Mooney-Rivlin']
        self.assertEqual(mr.find('c1').text, '3')
        self.assertEqual(mr.find('c2').text, '4')
        self.assertEqual(mr.find('k').text, '5')
        og = matls['Ogden']
        self.assertEqual(og.find('c1').text, '5')
        self.assertEqual(og.find('c2').text, '6')
        self.assertEqual(og.find('c3').text, '7')
        self.assertEqual(og.find('c4'), None)
        self.assertEqual(og.find('m1').text, '8')
        self.assertEqual(og.find('m2').text, '9')
        self.assertEqual(og.find('m3').text, '10')
        self.assertEqual(og.find('m4'), None)
        self.assertEqual(og.find('k').text, '11')
        rig = matls['rigid body']
        self.assertEqual(rig.find('center_of_mass').text, '13,14,15')
        self.assertEqual(rig.find('density'), None)
        trans = matls['trans iso Mooney-Rivlin']
        self.assertEqual(trans.find('c1').text, '20')
        self.assertEqual(trans.find('c2').text, '21')
        self.assertEqual(trans.find('c3').text, '16')
        self.assertEqual(trans.find('c4').text, '17')
        self.assertEqual(trans.find('c5').text, '18')
        self.assertEqual(trans.find('lam_max').text, '19')
        self.assertEqual(trans.find('k').text, '22')
        self.assertEqual(trans.find('fiber').get('type'), 'local')
        self.assertEqual(trans.find('fiber').text, '1,2')
        lin = matls['linear orthotropic']
        self.assertEqual(lin.find('E1').text, '23')
        self.assertEqual(lin.find('E2').text, '24')
        self.assertEqual(lin.find('E3').text, '25')
        self.assertEqual(lin.find('G12').text, '26')
        self.assertEqual(lin.find('G23').text, '27')
        self.assertEqual(lin.find('G31').text, '28')
        self.assertEqual(lin.find('v12').text, '29')
        self.assertEqual(lin.find('v23').text, '30')
        self.assertEqual(lin.find('v31').text, '31')
        self.assertEqual(lin.find('mat_axis').get('type'), 'local')
        self.assertEqual(lin.find('mat_axis').text, '1,3,4')
        fung = matls['Fung orthotropic']
        self.assertEqual(fung.find('mu1').text, '32')
        self.assertEqual(fung.find('mu2').text, '33')
        self.assertEqual(fung.find('mu3').text, '34')
        self.assertEqual(fung.find('l11').text, '35')
        self.assertEqual(fung.find('l22').text, '36')
        self.assertEqual(fung.find('l33').text, '37')
        self.assertEqual(fung.find('l12').text, '38')
        self.assertEqual(fung.find('l23').text, '39')
        self.assertEqual(fung.find('l31').text, '40')
        self.assertEqual(fung.find('c').text, '41')
        self.assertEqual(fung.find('k').text, '42')
        self.assertEqual(fung.find('mat_axis').get('type'), 'vector')
        self.assertEqual(fung.find('mat_axis').find('a').text, '0,0,1')
        self.assertEqual(fung.find('mat_axis').find('d').text, '1,0,1')
        trans2 = matls['trans iso Veronda-Westmann']
        self.assertEqual(trans2.find('c1').text, '47')
        self.assertEqual(trans2.find('c2').text, '48')
        self.assertEqual(trans2.find('c3').text, '43')
        self.assertEqual(trans2.find('c4').text, '44')
        self.assertEqual(trans2.find('c5').text, '45')
        self.assertEqual(trans2.find('lam_max').text, '46')
        self.assertEqual(trans2.find('k').text, '49')
        self.assertEqual(trans2.find('fiber').get('type'), 'user')
        # Check ElementData is created properly for this element.
        self.assertEqual( '0.25,0.25,0.25',
            tree.find('Geometry').find('ElementData').find('element').find('fiber').text )



class TestInp(unittest.TestCase):


    def test_read_inp(self):
        p = f.problem.FEproblem()
        p.read_inp(os.path.join(datadir, 'tf_joint.inp'))
        # Check all nodes and elements are accounted for.
        self.assertEqual(len(p.sets['tf_joint.inp:allnodes']), 96853)
        self.assertEqual(len(p.sets['tf_joint.inp:allelements']), 81653)
        self.assertEqual(len(p.elements), 81653 + 35604)
        # Check sets have found the correct nodes/elements.
        self.assertTrue( p.sets['tf_joint.inp:allnodes']['25225'] in
            p.sets['tf_joint.inp:f2fem'])
        self.assertFalse( p.sets['tf_joint.inp:allnodes']['1032'] in
            p.sets['tf_joint.inp:f2fem'])
        self.assertTrue( p.sets['tf_joint.inp:allelements']['52864'] in
            p.sets['tf_joint.inp:acl'])
        self.assertFalse( p.sets['tf_joint.inp:allelements']['9433'] in
            p.sets['tf_joint.inp:acl'])
        # Check all sets are accounted for.
        for xset in ('f2fem', 'tc2tib', 'tiblig', 'femlig', 'lmant', 'lmpost',
            'mmant', 'mmpost', 'femur', 'tibia', 'fcart', 'fcartr', 'fcartb',
            'fcartm', 'fcartt', 'tcart', 'tcartb', 'tcartm', 'tcartt', 'mcl',
            'amc', 'mmc', 'pmc', 'lcl', 'alc', 'mlc', 'plc', 'lat meni',
            'med meni', 'pcl', 'apc', 'ppc', 'acl', 'aclfiber', 'aac', 'pac',
            'femmcl', 'femlcl', 'mcltib', 'lcltib', 'fcs', 'fcsr', 'fcsm',
            'fcsl', 'tcs', 'tcsl', 'tcsm', 'mcls', 'mclsurf', 'lcls',
            'lclsurf', 'lmtib', 'lmfem', 'lmfemr', 'lmtibr', 'mmtib', 'mmfem',
            'mmfemr', 'mmtibr', 'pclsurf', 'aclsurf', ):
            self.assertTrue( 'tf_joint.inp:%s'%xset in p.sets,
                msg='Set %s not found' % xset )



class TestCnfg(unittest.TestCase):


    def test_read_cnfg(self):
        p = f.problem.FEproblem()
        p.read_cnfg(os.path.join(datadir, 'meniscectomy_kurosawa80.cnfg'))
        # TODO: Some actual tests.




if __name__=='__main__':
    unittest.main()
