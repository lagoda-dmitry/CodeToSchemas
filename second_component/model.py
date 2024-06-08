import abc
import os


TRUNK_COLOR = '#966F33'
LEAF_COLOR = '#6db33f'
EDGE_COLORS = ["#000000", "#E69F00", "#56B4E9", "#009E73",
               "#F0E442", "#0072B2", "#D55E00", "#CC79A7"]
NODE_COLOR = "#cccccc"


class Namespace(dict):

    def __init__(self, *args, **kwargs):
        d = {k: k for k in args}
        d.update(dict(kwargs.items()))
        super().__init__(d)

    def __getattr__(self, item):
        return self[item]


OWNER_CONST = Namespace("UNKNOWN_VAR", "UNKNOWN_MODULE")
GROUP_TYPE = Namespace("FILE", "CLASS", "NAMESPACE")


def is_installed(executable_cmd):

    for path in os.environ["PATH"].split(os.pathsep):
        path = path.strip('"')
        exe_file = os.path.join(path, executable_cmd)
        if os.path.isfile(exe_file) and os.access(exe_file, os.X_OK):
            return True
    return False


def djoin(*tup):

    if len(tup) == 1 and isinstance(tup[0], list):
        return '.'.join(tup[0])
    return '.'.join(tup)


def flatten(list_of_lists):

    return [el for sublist in list_of_lists for el in sublist]


def _resolve_str_variable(variable, file_groups):

    for file_group in file_groups:
        for node in file_group.all_nodes():
            if any(ot == variable.points_to for ot in node.import_tokens):
                return node
        for group in file_group.all_groups():
            if any(ot == variable.points_to for ot in group.import_tokens):
                return group
    return OWNER_CONST.UNKNOWN_MODULE


class BaseLanguage(abc.ABC):


    @staticmethod
    @abc.abstractmethod
    def assert_dependencies():
        

    @staticmethod
    @abc.abstractmethod
    def get_tree(filename, lang_params):
        

    @staticmethod
    @abc.abstractmethod
    def separate_namespaces(tree):
        

    @staticmethod
    @abc.abstractmethod
    def make_nodes(tree, parent):
        

    @staticmethod
    @abc.abstractmethod
    def make_root_node(lines, parent):
        

    @staticmethod
    @abc.abstractmethod
    def make_class_group(tree, parent):
        


class Variable():

    def __init__(self, token, points_to, line_number=None):

        assert token
        assert points_to
        self.token = token
        self.points_to = points_to
        self.line_number = line_number

    def __repr__(self):
        return f"<Variable token={self.token} points_to={repr(self.points_to)}"

    def to_string(self):

        if self.points_to and isinstance(self.points_to, (Group, Node)):
            return f'{self.token}->{self.points_to.token}'
        return f'{self.token}->{self.points_to}'


class Call():

    def __init__(self, token, line_number=None, owner_token=None, definite_constructor=False):
        self.token = token
        self.owner_token = owner_token
        self.line_number = line_number
        self.definite_constructor = definite_constructor

    def __repr__(self):
        return f"<Call owner_token={self.owner_token} token={self.token}>"

    def to_string(self):

        if self.owner_token:
            return f"{self.owner_token}.{self.token}()"
        return f"{self.token}()"

    def is_attr(self):

        return self.owner_token is not None

    def matches_variable(self, variable):


        if self.is_attr():
            if self.owner_token == variable.token:
                for node in getattr(variable.points_to, 'nodes', []):
                    if self.token == node.token:
                        return node
                for inherit_nodes in getattr(variable.points_to, 'inherits', []):
                    for node in inherit_nodes:
                        if self.token == node.token:
                            return node
                if variable.points_to in OWNER_CONST:
                    return variable.points_to

            if isinstance(variable.points_to, Group) \
               and variable.points_to.group_type == GROUP_TYPE.NAMESPACE:
                parts = self.owner_token.split('.')
                if len(parts) != 2:
                    return None
                if parts[0] != variable.token:
                    return None
                for node in variable.points_to.all_nodes():
                    if parts[1] == node.namespace_ownership() \
                       and self.token == node.token:
                        return node

            return None
        if self.token == variable.token:
            if isinstance(variable.points_to, Node):
                return variable.points_to
            if isinstance(variable.points_to, Group) \
               and variable.points_to.group_type == GROUP_TYPE.CLASS \
               and variable.points_to.get_constructor():
                return variable.points_to.get_constructor()
        return None


class Node():
    def __init__(self, token, calls, variables, parent, import_tokens=None,
                 line_number=None, is_constructor=False):
        self.token = token
        self.line_number = line_number
        self.calls = calls
        self.variables = variables
        self.import_tokens = import_tokens or []
        self.parent = parent
        self.is_constructor = is_constructor

        self.uid = "node_" + os.urandom(4).hex()

        self.is_leaf = True 
        self.is_trunk = True  

    def __repr__(self):
        return f"<Node token={self.token} parent={self.parent}>"

    def __lt__(self, other):
            return self.name() < other.name()

    def name(self):

        return f"{self.first_group().filename()}::{self.token_with_ownership()}"

    def first_group(self):

        parent = self.parent
        while not isinstance(parent, Group):
            parent = parent.parent
        return parent

    def file_group(self):

        parent = self.parent
        while parent.parent:
            parent = parent.parent
        return parent

    def is_attr(self):

        return (self.parent
                and isinstance(self.parent, Group)
                and self.parent.group_type in (GROUP_TYPE.CLASS, GROUP_TYPE.NAMESPACE))

    def token_with_ownership(self):

        if self.is_attr():
            return djoin(self.parent.token, self.token)
        return self.token

    def namespace_ownership(self):

        parent = self.parent
        ret = []
        while parent and parent.group_type == GROUP_TYPE.CLASS:
            ret = [parent.token] + ret
            parent = parent.parent
        return djoin(ret)

    def label(self):

        if self.line_number is not None:
            return f"{self.line_number}: {self.token}()"
        return f"{self.token}()"

    def remove_from_parent(self):

        self.first_group().nodes = [n for n in self.first_group().nodes if n != self]

    def get_variables(self, line_number=None):

        if line_number is None:
            ret = list(self.variables)
        else:
            ret = list([v for v in self.variables if v.line_number <= line_number])
        if any(v.line_number for v in ret):
            ret.sort(key=lambda v: v.line_number, reverse=True)

        parent = self.parent
        while parent:
            ret += parent.get_variables()
            parent = parent.parent
        return ret

    def resolve_variables(self, file_groups):

        for variable in self.variables:
            if isinstance(variable.points_to, str):
                variable.points_to = _resolve_str_variable(variable, file_groups)
            elif isinstance(variable.points_to, Call):
                call = variable.points_to
                if call.is_attr() and not call.definite_constructor:
                    continue

                for file_group in file_groups:
                    for group in file_group.all_groups():
                        if group.token == call.token:
                            variable.points_to = group
            else:
                assert isinstance(variable.points_to, (Node, Group))

    def to_dot(self):

        attributes = {
            'label': self.label(),
            'name': self.name(),
            'shape': "rect",
            'style': 'rounded,filled',
            'fillcolor': NODE_COLOR,
        }
        if self.is_trunk:
            attributes['fillcolor'] = TRUNK_COLOR
        elif self.is_leaf:
            attributes['fillcolor'] = LEAF_COLOR

        ret = self.uid + ' ['
        for k, v in attributes.items():
            ret += f'{k}="{v}" '
        ret += ']'
        return ret

    def to_dict(self):

        return {
            'uid': self.uid,
            'label': self.label(),
            'name': self.name(),
        }


def _wrap_as_variables(sequence):

    return [Variable(el.token, el, el.line_number) for el in sequence]


class Edge():
    def __init__(self, node0, node1):
        self.node0 = node0
        self.node1 = node1


        node0.is_leaf = False
        node1.is_trunk = False

    def __repr__(self):
        return f"<Edge {self.node0} -> {self.node1}"

    def __lt__(self, other):
        if self.node0 == other.node0:
            return self.node1 < other.node1
        return self.node0 < other.node0

    def to_dot(self):
        '''
        Returns string format for embedding in a dotfile. Example output:
        node_uid_a -> node_uid_b [color='#aaa' penwidth='2']
        :rtype: str
        '''
        ret = self.node0.uid + ' -> ' + self.node1.uid
        source_color = int(self.node0.uid.split("_")[-1], 16) % len(EDGE_COLORS)
        ret += f' [color="{EDGE_COLORS[source_color]}" penwidth="2"]'
        return ret

    def to_dict(self):

        return {
            'source': self.node0.uid,
            'target': self.node1.uid,
            'directed': True,
        }


class Group():

    def __init__(self, token, group_type, display_type, import_tokens=None,
                 line_number=None, parent=None, inherits=None):
        self.token = token
        self.line_number = line_number
        self.nodes = []
        self.root_node = None
        self.subgroups = []
        self.parent = parent
        self.group_type = group_type
        self.display_type = display_type
        self.import_tokens = import_tokens or []
        self.inherits = inherits or []
        assert group_type in GROUP_TYPE

        self.uid = "cluster_" + os.urandom(4).hex()  # group doesn't work by syntax rules

    def __repr__(self):
        return f"<Group token={self.token} type={self.display_type}>"

    def __lt__(self, other):
        return self.label() < other.label()

    def label(self):

        return f"{self.display_type}: {self.token}"

    def filename(self):

        if self.group_type == GROUP_TYPE.FILE:
            return self.token
        return self.parent.filename()

    def add_subgroup(self, sg):

        self.subgroups.append(sg)

    def add_node(self, node, is_root=False):

        self.nodes.append(node)
        if is_root:
            self.root_node = node

    def all_nodes(self):

        ret = list(self.nodes)
        for subgroup in self.subgroups:
            ret += subgroup.all_nodes()
        return ret

    def get_constructor(self):

        assert self.group_type == GROUP_TYPE.CLASS
        constructors = [n for n in self.nodes if n.is_constructor]
        if constructors:
            return constructors[0]

    def all_groups(self):

        ret = [self]
        for subgroup in self.subgroups:
            ret += subgroup.all_groups()
        return ret

    def get_variables(self, line_number=None):


        if self.root_node:
            variables = (self.root_node.variables
                         + _wrap_as_variables(self.subgroups)
                         + _wrap_as_variables(n for n in self.nodes if n != self.root_node))
            if any(v.line_number for v in variables):
                return sorted(variables, key=lambda v: v.line_number, reverse=True)
            return variables
        else:
            return []

    def remove_from_parent(self):

        if self.parent:
            self.parent.subgroups = [g for g in self.parent.subgroups if g != self]

    def all_parents(self):
  
        if self.parent:
            return [self.parent] + self.parent.all_parents()
        return []

    def to_dot(self):


        ret = 'subgraph ' + self.uid + ' {\n'
        if self.nodes:
            ret += '    '
            ret += ' '.join(node.uid for node in self.nodes)
            ret += ';\n'
        attributes = {
            'label': self.label(),
            'name': self.token,
            'style': 'filled',
        }
        for k, v in attributes.items():
            ret += f'    {k}="{v}";\n'
        ret += '    graph[style=dotted];\n'
        for subgroup in self.subgroups:
            ret += '    ' + ('\n'.join('    ' + ln for ln in
                                       subgroup.to_dot().split('\n'))).strip() + '\n'
        ret += '};\n'
        return ret
