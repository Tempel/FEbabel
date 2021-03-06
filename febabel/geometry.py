from math import sqrt
from .common import Base, Constrainable

class Node(Constrainable):
    """A single point in three-dimensional Cartesian space.
    The node coordinates can be accessed and set through properties x,y,z.
    Similarly, coordinates can be indexed and iterated over like a list."""

    # Only one piece of data needs storing, so use slots to decrease memory.
    __slots__ = ['_pos']


    def __init__(self, pos):
        """Create a node at the given position.
        pos must be an iterable of length 3.
        NOTE: This will not protect you from yourself!  Insert *only* valid
        data (length 3 sequence of ints/floats), or the result will be
        undefined!"""
        Constrainable.__init__(self, 'x','y','z')
        p = iter(pos)
        self._pos = [p.next(), p.next(), p.next()]


    # Special properties getters/setters.
    def _getx(self):
        return self._pos[0]
    def _setx(self, value):
        self._pos[0] = value
    x = property(_getx, _setx)

    def _gety(self):
        return self._pos[1]
    def _sety(self, value):
        self._pos[1] = value
    y = property(_gety, _sety)

    def _getz(self):
        return self._pos[2]
    def _setz(self, value):
        self._pos[2] = value
    z = property(_getz, _setz)


    # So a Node object can be treated like a list.
    def __iter__(self):
        return iter(self._pos)
    def __getitem__(self, i):
        return self._pos[i]
    def __setitem__(self, i, value):
        self._pos[i] = value
    def __len__(self):
        # Could return len(self._pos), but it will always be 3...
        return 3

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, repr(self._pos))

    def distance_to(self, node):
        "Returns Euclidean distance between this node and a given one."
        return sqrt(sum( (i-j)**2 for i,j in zip(self, node) ))



class Element(Base):
    """Base class for all different element types.
    Note that subclasses should define n_nodes, the number of nodes required by
    the particular element."""

    # Only this data needs storing, so decrease memory again.
    # Note that this doesn't interfere with adding new data to the class
    # directly; only instances are affected.  Adding n_nodes is fine.
    __slots__ = ['_nodes', 'material']

    def __init__(self, nodes, material=None):
        """nodes is an iterable of Node objects.
        material is a Material object, or None.
        NOTE: This will not protect you from yourself!  Insert *only* valid
        data (a correct-length sequence of nodes), or the result will be
        undefined!"""
        n = iter(nodes)
        self._nodes = [ n.next() for i in xrange(self.n_nodes) ]
        self.material = material

    def get_children(self):
        s = set(self._nodes)
        s.add(self.material)
        s.discard(None)
        return s


    # Mathematical properties of the element.
    def get_vertex_avg(self):
        "Calculate the average location of all nodes in this element."
        x = sum( n[0] for n in self._nodes ) / float(self.n_nodes)
        y = sum( n[1] for n in self._nodes ) / float(self.n_nodes)
        z = sum( n[2] for n in self._nodes ) / float(self.n_nodes)
        return (x,y,z)


    # So an Element object can be treated like a list.
    def __iter__(self):
        return iter(self._nodes)
    def __getitem__(self, i):
        return self._nodes[i]
    def __setitem__(self, i, node):
        self._nodes[i] = node
    def __len__(self):
        # Could return len(self._nodes), but it will always be constant...
        return self.n_nodes

    def __repr__(self):
        return "%s(%s, %s)" % ( self.__class__.__name__, repr(self._nodes),
            repr(self.material) )


class SolidElement(Element):
    "Base class for 3D solid elements."

class Tet4(SolidElement):
    "4-node linear tetrahedral element."
    n_nodes = 4
class Pent6(SolidElement):
    "6-node linear pentahedral (triangular prism) element."
    n_nodes = 6
class Hex8(SolidElement):
    "8-node linear hexahedral (brick) element."
    n_nodes = 8


class ShellElement(Element):
    "Base class for shell elements."
    __slots__ = ['thickness']
    # TODO: thickness should be a list; one for each node.
    def __init__(self, nodes, material=None, thickness=0.0):
        Element.__init__(self, nodes, material)
        self.thickness = thickness

class Shell3(ShellElement):
    "3-node triangular shell element."
    n_nodes = 3
class Shell4(ShellElement):
    "4-node quadrilateral shell element."
    n_nodes = 4


class SurfaceElement(Element):
    "Base class for surface elements."

class Surface3(SurfaceElement):
    "3-node triangular surface element."
    n_nodes = 3
class Surface4(SurfaceElement):
    "4-node quadrilateral surface element."
    n_nodes = 4


class Spring(Element):
    "2-node linear spring element."
    n_nodes = 2
    def __init__(self, nodes, material=None, tension_only=False):
        self.tension_only = tension_only
        Element.__init__(self, nodes, material)
