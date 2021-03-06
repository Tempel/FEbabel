"""
Contains a method for writing an FEproblem to FEBio's .feb format.

Supports .feb version 1.1.
"""

from warnings import warn
from itertools import chain

from .. import geometry as geo, materials as mat, constraints as con, problem, common


# Data for converting internal objects to FEBio's form.

geo.Tet4._name_feb = 'tet4'
geo.Pent6._name_feb = 'pent6'
geo.Hex8._name_feb = 'hex8'
geo.Shell3._name_feb = 'tri3'
geo.Shell4._name_feb = 'quad4'
geo.Surface3._name_feb = 'tri3'
geo.Surface4._name_feb = 'quad4'
# Spring elements are handled differently, so not included.

mat.LinearIsotropic._name_feb = 'isotropic elastic'
mat.NeoHookean._name_feb = 'neo-Hookean'
mat.HolmesMow._name_feb = 'Holmes-Mow'
mat.MooneyRivlin._name_feb = 'Mooney-Rivlin'
mat.VerondaWestmann._name_feb = 'Veronda-Westmann'
mat.ArrudaBoyce._name_feb = 'Arruda-Boyce'
mat.Ogden._name_feb = 'Ogden'
mat.Rigid._name_feb = 'rigid body'
# TransIsoElastic is not a wrapper type in FEBio; its name depends on its base
# material.  NOTE: Only Mooney-Rivlin and Veronda-Westmann are supported as
# base types by FEBio, but this is not checked by write_feb.
mat.TransIsoElastic._name_feb = property(
    lambda self: 'trans iso %s' % self.base._name_feb )
mat.LinearOrthotropic._name_feb = 'linear orthotropic'
mat.FungOrthotropic._name_feb = 'Fung orthotropic'

def _name_feb_SlidingContact(self):
    # TODO: Warnings or errors if options can't be used together.
    if self.solute:
        return 'sliding3'
    elif self.biphasic:
        return 'sliding2'
    elif self.friction_coefficient:
        return 'sliding_with_gaps'
    else:
        return 'facet-to-facet sliding'
con.SlidingContact._name_feb = property(_name_feb_SlidingContact)
con.TiedContact._name_feb = 'tied'
con.RigidInterface._name_feb = 'rigid'

loadcurve_interp_map = {
    con.LoadCurve.IN_LINEAR: 'linear',
    con.LoadCurve.IN_STEP: 'step',
    con.LoadCurve.IN_CUBIC_SPLINE: 'smooth',
}
loadcurve_extrap_map = {
    con.LoadCurve.EX_CONSTANT: 'constant',
    con.LoadCurve.EX_TANGENT: 'tangent',
    con.LoadCurve.EX_REPEAT: 'repeat',
    con.LoadCurve.EX_REPEAT_OFFSET: 'repeat offset',
}


# Methods to get dictionary of parameters.
# Each key is a string in the form used in FEBio to represent the parameter.
# Note that all current materials have their parameters named in the same way
# as FEBio, so no conversions are yet necessary.
def _params_feb(self):
    return dict( (k, str(getattr(self, k))) for k in self.parameters )
mat.Material._params_feb = _params_feb

# Ogden's parameters list requires it have a slightly different approach.
def _params_feb_Ogden(self):
    d = dict()
    for i,v in enumerate(self.ci if len(self.ci) <= 6 else self.ci[:6]):
        d['c%s' % (i+1)] = str(v)
    for i,v in enumerate(self.mi if len(self.mi) <= 6 else self.mi[:6]):
        d['m%s' % (i+1)] = str(v)
    d['k'] = str(self.k)
    return d
mat.Ogden._params_feb = _params_feb_Ogden

# Rigid center of mass needs combining into one string.
def _params_feb_Rigid(self):
    d = dict()
    if self.center_of_mass is not None:
        d['center_of_mass'] = ','.join(map(str, self.center_of_mass))
    if self.density is not None:
        d['density'] = str(self.density)
    if not d:
        warn('A rigid body must have at least one of density or center of mass.')
    return d
mat.Rigid._params_feb = _params_feb_Rigid

# Since TransIsoElastic is not a wrapper type in FEBio, the parameters of its
# base material must be added to its own parameters.
def _params_feb_TransIso(self):
    d = mat.Material._params_feb(self)
    del d['base'], d['axis']
    d.update(self.base._params_feb())

    ax = self.axis
    if isinstance(ax, mat.VectorOrientation):
        d['fiber'] = ( 'vector', ','.join(map(str,ax.pos1)) )
    elif isinstance(ax, mat.SphericalOrientation):
        d['fiber'] = ( 'spherical', ','.join(map(str,ax.pos1)) )
    elif isinstance(ax, mat.NodalOrientation):
        d['fiber'] = ( 'local', ','.join(str(n+1) for n in ax.edge1) )
    else:
        d['fiber'] = ('user', '')

    return d
mat.TransIsoElastic._params_feb = _params_feb_TransIso

def _params_Ortho(self):
    d = mat.Material._params_feb(self)
    del d['axis']

    ax = self.axis
    if isinstance(ax, mat.VectorOrientation):
        d['mat_axis'] = ( 'vector',
            {'a':','.join(map(str, ax.pos1)),
            'd':','.join(map(str, ax.pos2))} )
    elif isinstance(ax, mat.NodalOrientation):
        d['mat_axis'] = ( 'local',
            '%s,%s,%s' % (ax.edge1[0]+1, ax.edge1[1]+1, ax.edge2[1]+1) )
    else:
        warn('Inappropriate axis type for orthotropic material in FEBio.')
    return d
mat.OrthoMaterial._params_feb = _params_Ortho



def write(self, file_name_or_obj):
    """Write out the current problem state to an FEBio .feb file.
    NOTE: Not all nuances of the state can be fully represented."""

    import xml.etree.ElementTree as etree

    descendants = self.get_descendants_sorted()

    e_root = etree.Element('febio_spec',
        {'version': '1.1'})

    e_control = etree.SubElement(e_root, 'Control')
    # TODO: Control stuff.


    e_material = etree.SubElement(e_root, 'Material')
    matl_ids = dict()
    matl_ids[None] = '0'
    # Set of materials requiring per-element orientation data in ElementData.
    matl_user_orient = set()

    # FIXME: These material removals could potentially break something if the
    # material is used both as a TransIsoElastic base and directly in an
    # element.  If that happens, a KeyError will probably result.
    #
    # TransIsoElastic materials are not treated as wrappers in FEBio, so don't
    # add their base materials to FEBio's list.
    top_materials = set(descendants[mat.Material])
    for m in descendants[mat.Material]:
        if isinstance(m, mat.TransIsoElastic):
            top_materials.discard(m.base)
    # Spring elements have a very different approach to materials, so don't
    # add them to FEBio's list either.
    for e in descendants[geo.Element]:
        if isinstance(e, geo.Spring):
            top_materials.discard(e.material)

    for i,m in enumerate(top_materials):
        mid = str(i+1)
        # TODO: Some materials will have submaterials.  These will need to be
        # created first (maybe?), then referenced by the wrapper material.
        matl_ids[m] = mid

        # Create matl, set its name and ID number.
        e_mat = etree.SubElement(e_material, 'material', {'id':mid,
            'type': m._name_feb})
        # Create matl parameters.
        # The _params_feb method returns a dictionary, with string keys.
        for k,v in m._params_feb().iteritems():
            e_param = etree.SubElement(e_mat, k)
            if isinstance(v, basestring):
                e_param.text = v

            # If value is a tuple, first entry is 'type' attrib, second is text.
            else:
                e_param.set('type', v[0])
                # Note if this material needs user orientation data.
                if v[0] == 'user': matl_user_orient.add(m)

                if isinstance(v[1], basestring):
                    e_param.text = v[1]
                # If second tuple value is a dict, these are parameters for the
                # parameter (only vector ortho materials need this).
                else:
                    for kk, vv in v[1].iteritems():
                        e_pp = etree.SubElement(e_param, kk)
                        e_pp.text = vv


    e_geometry = etree.SubElement(e_root, 'Geometry')
    node_ids = dict()
    elem_ids = dict()

    # Write out all nodes.  In the process, store the ID of each in a
    # dictionary indexed by node object for fast retrieval later.
    e_nodes = etree.SubElement(e_geometry, 'Nodes')
    for i,n in enumerate(descendants[geo.Node]):
        nid = str(i+1)
        e_node = etree.SubElement(e_nodes, 'node', {'id':nid})
        e_node.text = ','.join( map(str,iter(n)) )
        node_ids[n] = nid

    e_elements = etree.SubElement(e_geometry, 'Elements')
    # Get list of only those elements that FEBio lists in the Elements section.
    elements = [ e for e in descendants[geo.Element]
        if isinstance(e, (geo.SolidElement, geo.ShellElement)) ]
    for i,e in enumerate(elements):
        eid = str(i+1)
        elem_ids[e] = eid
        e_elem = etree.SubElement(e_elements, e._name_feb,
            {'id':eid, 'mat':matl_ids[e.material]})
        e_elem.text = ','.join( node_ids[n] for n in iter(e) )

    e_elemdata = etree.SubElement(e_geometry, 'ElementData')
    for e in ( e for e in descendants[geo.Element]
        if isinstance(e, geo.ShellElement) or e.material in matl_user_orient ):

        e_elem = etree.SubElement(e_elemdata, 'element', {'id':elem_ids[e]})
        if e.material in matl_user_orient:
            e_fiber = etree.SubElement(e_elem, 'fiber')
            e_fiber.text = ','.join(map(str,e.material.axis.get_at_element(e)[0]))
        if isinstance(e, geo.ShellElement):
            # TODO: Per-node thickness.  Currently forces constant thickness
            # throughout shell.
            e_thick = etree.SubElement(e_elem, 'thickness')
            e_thick.text = ','.join( [str(e.thickness)]*len(e) )
    if len(e_elemdata) == 0:
        e_geometry.remove(e_elemdata)


    # Loadcurves must be processed before constraints, but the LoadData element
    # comes later in the feb file.  Create the element here, then append later.
    e_loaddata = etree.Element('LoadData')
    loadcurve_ids = dict()
    # FIXME: Includes loadcurve_zero, which is typically not necessary (but how
    # do you know for certain?)
    # FIXME: FEBio's behaviour with step interpolation is weird.  Possibly
    # translate values to use a more sane form of step interpolation.
    # TODO: A loadcurve is needed to set must points.  This will probably
    # involve having some kind of must point object taking a loadcurve.
    for i,lc in enumerate(descendants[con.LoadCurve]):
        lcid = str(i+1)
        loadcurve_ids[lc] = lcid
        e_loadcurve = etree.SubElement( e_loaddata, 'loadcurve',
            {'id': lcid,
            'type': loadcurve_interp_map[lc.interpolation],
            'extend': loadcurve_extrap_map[lc.extrapolation]} )
        for time in sorted(lc.points.iterkeys()):
            e_loadpoint = etree.SubElement(e_loadcurve, 'loadpoint')
            e_loadpoint.text = '%s,%s' % (time, lc.points[time])


    e_boundary = etree.SubElement(e_root, 'Boundary')

    # Apply constraints on nodes.
    e_prescribe = etree.SubElement(e_boundary, 'prescribe')
    e_fix = etree.SubElement(e_boundary, 'fix')
    e_force = etree.SubElement(e_boundary, 'force')
    # TODO: All boundary conditions related to surfaces (pressure, flux, etc.)

    switched_nodes = set()
    for node,nid in node_ids.iteritems():
        for dof,constraint in node.constraints.iteritems():
            if constraint is con.free:
                pass
            elif constraint is con.fixed:
                etree.SubElement(e_fix, 'node', {'id':nid, 'bc':dof})
            elif isinstance(constraint, con.Displacement):
                e = etree.SubElement(e_prescribe, 'node', {'id':nid, 'bc':dof,
                    'lc':loadcurve_ids[constraint.loadcurve]})
                e.text = repr(constraint.multiplier)
            elif isinstance(constraint, con.Force):
                e = etree.SubElement(e_force, 'node', {'id':nid, 'bc':dof,
                    'lc':loadcurve_ids[constraint.loadcurve]})
                e.text = repr(constraint.multiplier)
            elif isinstance(constraint, con.SwitchConstraint):
                switched_nodes.add(node) # We'll deal with this farther down.
            else:
                warn("Don't recognize constraint on node.")


    # Separate switched contact interfaces from global ones.
    switched_contact = descendants[con.Contact] & descendants[common.Switch]
    global_contact = descendants[con.Contact] - switched_contact
    for s in switched_contact:
        for c in s.points.itervalues():
            global_contact.discard(c)

    # Apply global contact interfaces.
    for contact in global_contact:
        e_contact = etree.SubElement(e_boundary, 'contact',
                                     {'type': contact._name_feb})
        if isinstance(contact, con.RigidInterface):
            mid = matl_ids[contact.rigid_body]
            for node in contact.nodes:
                etree.SubElement(e_contact, 'node',
                                 {'id': node_ids[node], 'rb': mid})
        else:
            # Apply solution-specific options.
            for opt,val in contact.options.iteritems():
                e = etree.SubElement(e_contact, opt)
                e.text = val

            # Define both contact surfaces.
            e_master = etree.SubElement(e_contact, 'surface',{'type':'master'})
            for i,elem in enumerate(contact.master):
                e = etree.SubElement(e_master, elem._name_feb,
                                     {'id': str(i+1)})
                e.text = ','.join(node_ids[n] for n in iter(elem))

            e_slave = etree.SubElement(e_contact, 'surface', {'type': 'slave'})
            for i,elem in enumerate(contact.slave):
                e = etree.SubElement(e_slave, elem._name_feb,
                                     {'id': str(i+1)})
                e.text = ','.join(node_ids[n] for n in iter(elem))


    # Create spring elements.
    for e in descendants[geo.Element] :
        if not isinstance(e, geo.Spring):
            continue
        # TODO: Support for nonlinear springs.
        e_spring = etree.SubElement(e_boundary, 'spring',
            {'type': 'tension-only linear' if e.tension_only else 'linear'})
        e_node = etree.SubElement(e_spring, 'node')
        e_node.text = ','.join(node_ids[n] for n in iter(e))
        if not isinstance(e.material, mat.LinearIsotropic):
            warn('Support for nonlinear springs is not yet implemented.')
        e_E = etree.SubElement(e_spring, 'E')
        e_E.text = repr(e.material.E)


    # Remove any sections that aren't needed.
    for e in (e_prescribe, e_fix, e_force):
        if len(e) == 0:
            e_boundary.remove(e)
    if len(e_boundary) == 0:
        e_root.remove(e_boundary)


    # Apply constraints on rigid bodies.
    e_constraints = etree.SubElement(e_root, 'Constraints')

    switched_rigid = set()
    for matl,mid in matl_ids.iteritems():
        if not isinstance(matl, common.Constrainable):
            continue
        e_rigid = etree.SubElement(e_constraints, 'rigid_body', {'mat':mid})

        for dof,tag in zip(('x','y','z','Rx','Ry','Rz'),
            ('trans_x', 'trans_y', 'trans_z', 'rot_x', 'rot_y', 'rot_z') ):

            constraint = matl.constraints[dof]

            if constraint is con.free:
                continue
            elif isinstance(constraint, con.SwitchConstraint):
                switched_rigid.add(matl) # We'll deal with this farther down.
                continue

            e = etree.SubElement(e_rigid, tag)
            if constraint is con.fixed:
                e.set('type', 'fixed')
            elif isinstance(constraint, con.Displacement):
                e.set('type', 'prescribed')
                e.set('lc', loadcurve_ids[constraint.loadcurve])
                e.text = repr(constraint.multiplier)
            elif isinstance(constraint, con.Force):
                e.set('type', 'force')
                e.set('lc', loadcurve_ids[constraint.loadcurve])
                e.text = repr(constraint.multiplier)
            else:
                warn("Don't recognize constraint on rigid body.")

        # Remove rigid body constraints section if not needed.
        if len(e_rigid) == 0:
            e_constraints.remove(e_rigid)

    # Remove Constraints section if not needed.
    if len(e_constraints) == 0:
        e_root.remove(e_constraints)


    # After Constraints element, insert LoadData element.
    e_root.append(e_loaddata)


    # Write out Steps.

    # Parse all Switch objects to determine all the times at which they change
    # state.  Iterate through all those time changes in order.
    for time in sorted(set(chain(
            *[s.points.iterkeys() for s in descendants[common.Switch]] ))):

        e_step = etree.SubElement(e_root, 'Step')

        # TODO: Control section.


        # Boundary section for this step.
        # (Mostly copy-pasted from global Boundary section.)
        eS_boundary = etree.SubElement(e_step, 'Boundary')

        eS_prescribe = etree.SubElement(eS_boundary, 'prescribe')
        eS_fix = etree.SubElement(eS_boundary, 'fix')
        eS_force = etree.SubElement(eS_boundary, 'force')

        for node in switched_nodes:
            nid = node_ids[node]
            for dof,constraint in node.constraints.iteritems():
                if not isinstance(constraint, con.SwitchConstraint):
                    continue

                active = constraint.get_active(time)
                if active is con.free:
                    pass
                elif active is con.fixed:
                    etree.SubElement(eS_fix, 'node', {'id':nid, 'bc':dof})
                elif isinstance(active, con.Displacement):
                    e = etree.SubElement(eS_prescribe, 'node', {'id':nid,
                        'bc':dof, 'lc':loadcurve_ids[active.loadcurve]})
                    e.text = repr(active.multiplier)
                elif isinstance(active, con.Force):
                    e = etree.SubElement(eS_force, 'node', {'id':nid,
                        'bc':dof, 'lc':loadcurve_ids[active.loadcurve]})
                    e.text = repr(active.multiplier)
                else:
                    warn("Don't recognize constraint in switch on node.")


        for contact in switched_contact:
            active = contact.get_active(time)
            if active is None:
                continue
            e_contact = etree.SubElement(eS_boundary, 'contact',
                                         {'type': active._name_feb})
            if isinstance(active, con.RigidInterface):
                mid = matl_ids[active.rigid_body]
                for node in active.nodes:
                    etree.SubElement(e_contact, 'node',
                                     {'id': node_ids[node], 'rb': mid})
            else:
                # Apply solution-specific options.
                for opt,val in active.options.iteritems():
                    e = etree.SubElement(e_contact, opt)
                    e.text = val

                # Define both contact surfaces.
                e_master = etree.SubElement(e_contact, 'surface',{'type':'master'})
                for i,elem in enumerate(active.master):
                    e = etree.SubElement(e_master, elem._name_feb,
                                         {'id': str(i+1)})
                    e.text = ','.join(node_ids[n] for n in iter(elem))

                e_slave = etree.SubElement(e_contact, 'surface', {'type': 'slave'})
                for i,elem in enumerate(active.slave):
                    e = etree.SubElement(e_slave, elem._name_feb,
                                         {'id': str(i+1)})
                    e.text = ','.join(node_ids[n] for n in iter(elem))


        # Remove any sections that aren't needed.
        for e in (eS_prescribe, eS_fix, eS_force):
            if len(e) == 0:
                eS_boundary.remove(e)
        if len(eS_boundary) == 0:
            e_step.remove(eS_boundary)


        # Constraints section for this step.
        # (Mostly copy-pasted from global Constraints section.)
        eS_constraints = etree.SubElement(e_step, 'Constraints')

        for matl in switched_rigid:
            mid = matl_ids[matl]
            eS_rigid = etree.SubElement(eS_constraints, 'rigid_body', {'mat':mid})

            for dof,tag in zip(('x','y','z','Rx','Ry','Rz'),
                ('trans_x', 'trans_y', 'trans_z', 'rot_x', 'rot_y', 'rot_z') ):

                constraint = matl.constraints[dof]
                if not isinstance(constraint, con.SwitchConstraint):
                    continue
                active = constraint.get_active(time)
                if active is con.free:
                    continue

                e = etree.SubElement(eS_rigid, tag)
                if active is con.fixed:
                    e.set('type', 'fixed')
                elif isinstance(active, con.Displacement):
                    e.set('type', 'prescribed')
                    e.set('lc', loadcurve_ids[active.loadcurve])
                    e.text = repr(active.multiplier)
                elif isinstance(active, con.Force):
                    e.set('type', 'force')
                    e.set('lc', loadcurve_ids[active.loadcurve])
                    e.text = repr(active.multiplier)
                else:
                    warn("Don't recognize constraint in switch on rigid body.")

            # Remove rigid body constraints section if not needed.
            if len(eS_rigid) == 0:
                eS_constraints.remove(eS_rigid)

        # Remove Constraints section if not needed.
        if len(eS_constraints) == 0:
            e_step.remove(eS_constraints)



    etree.ElementTree(e_root).write(file_name_or_obj, encoding='UTF-8')




problem.FEproblem.write_feb = write
