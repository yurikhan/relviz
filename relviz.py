#!/usr/bin/python3

import argparse
from itertools import groupby
import logging
from operator import attrgetter
import os.path
import sys

import networkx as nx
import pygraphviz as gv

import fact_parser


def group_sorted(xs, key):
    return groupby(sorted(xs, key=key), key=key)

def updated(*dicts):
    result = {}
    for each in dicts:
        result.update(each)
    return result


class FactModel:
    """
    Object representation of a set of facts.

    * `self.object_facts` and `self.relation_facts`
       partition the original facts by kind.
    * `self.generalzations` contains the names of relations
       that descend from `generalization`.
    * `self.objects` represents each object as mentioned in facts
      as a Python class.
      For each `o` in `self.objects`:

      * `o.__name__` is the object name;
      * `o.__bases__` are objects with which `o` is in a direct
        generalization relation;
      * `o.direct_attrs` is the dictionary of attributes defined
        directly on the `o` object fact(s);
      * `o.attrs` is the dictionary of attributes collected from `o`
        and all its ancestors, in C3 linearization order.
    """
    @staticmethod
    def _find_generalizations(relations):
        """
        Return the set of names that directly or indirectly
        descend from `generalization`.
        """
        result = set()
        queue = {'generalization'}
        while queue:
            current = queue.pop()
            result.add(current)
            queue.update(r.lhs for r in relations
                         if r.lhs not in result
                         and r.rel in result
                         and r.rhs in result)
        return result

    def __init__(self, facts):
        self.object_facts = [o for o in facts if 'type' in o]
        self.relation_facts = [r for r in facts if 'rel' in r]
        self.generalizations = self._find_generalizations(self.relation_facts)
        logging.getLogger(__name__).debug(
            '%d generalizations found', len(self.generalizations))

        network = nx.DiGraph()
        groups = group_sorted((r for r in self.relation_facts
                               if r.rel in self.generalizations),
                              key=attrgetter('lhs'))
        network.add_nodes_from(
            (name, {'bases': [r.rhs for r in rs]})
            for name, rs in groups)
        network.add_edges_from((r.lhs, r.rhs) for r in self.relation_facts
                               if r.rel in self.generalizations)
        objects = {}
        for name in nx.topological_sort(network, reverse=True):
            logging.getLogger(__name__).debug('Creating class for %s', name)
            objects[name] = type(
                name,
                tuple(objects[base_name]
                      for base_name in network.node[name].get('bases', [])),
                {})
            objects[name].direct_attrs = {}
        for o in self.object_facts:
            logging.getLogger(__name__).debug('Combining attributes for %s', o.name)
            if o.name not in objects:
                objects[o.name] = type(o.name, (), {})
                objects[o.name].direct_attrs = {}
            objects[o.name].direct_attrs.update(o.attrs.asDict())
        for o in objects.values():
            o.attrs = updated(*(objects[base.__name__].direct_attrs
                                for base in reversed(o.__mro__)
                                if base is not object))
        self.objects = objects

    def __getitem__(self, name):
        return self.objects[name].attrs if name in self.objects else {}


def parse_args():
    ap = argparse.ArgumentParser(
        description='Render facts as a GraphViz graph.')
    ap.add_argument('-v', '--verbose', action='store_true',
        help='Produce debugging output')
    ap.add_argument('--default-style', action='store_true', default=True,
        help='Use default style [default]')
    ap.add_argument('--no-default-style', action='store_false',
        dest='default-style',
        help='Do not use default style')
    ap.add_argument('-s', '--style', type=argparse.FileType('r'),
        help='Style file [none]')
    ap.add_argument('facts', type=argparse.FileType('r'),
        default=sys.stdin,
        help='Facts file [stdin]')
    ap.add_argument('-o', '--output', type=argparse.FileType('w'),
        default=sys.stdout,
        help='Output file [stdout]')

    return ap.parse_args()


def load_default_style():
    for path in [os.path.dirname(__file__), '/usr/share/relviz']:
        try:
            style_path = os.path.join(path, 'uml-1.5.style')
            with open(style_path) as style_file:
                logging.getLogger(__name__).debug('Loaded %s', style_path)
                return style_file.read()
        except:
            continue
    logging.getLogger(__name__).debug('Using barebone default style')
    return ('edge-type is, are, is-a, is-an, generalizes, subclasses '
            'generalization generalization')


class GraphError(ValueError):
    pass


def transitive_reduce(g):
    """
    Remove as many edges from `g` as possible while preserving reachability.
    """
    def _process(g, u, v, done):
        if v in done:
            return
        for w in list(g[v]):
            g.remove_edge(u, w)
            _process(g, u, w, done)
        done.add(v)

    for u in g:
        done = set()
        for v in list(g[u]):
            _process(g, u, v, done)


def build_clusters(objects, relations, styles_by_type):
    """
    Return a graph whose vertices are names of objects mapping to clusters,
    edges represent direct containment of clusters
    and every cluster is directly contained in at most one parent cluster.

    Raises `GraphError` if such a graph cannot be built.
    """
    result = nx.DiGraph()
    for o in objects:
        if o.type in styles_by_type.get('cluster-type', set()):
            result.add_node(o.name, {'type': o.type, 'attrs': o.attrs.asDict()})
    result.add_edges_from(
        (r.lhs, r.rhs) for r in relations
        if r.rel in styles_by_type.get('containment', set())
        and r.lhs in result and r.rhs in result)
    try:
        cycle = nx.find_cycle(result)
    except nx.exception.NetworkXNoCycle:
        pass
    else:
        raise GraphError('Circular containment: %s in %s'
                         % (cycle[0][0], ' in '.join(v for u, v in cycle)))

    transitive_reduce(result)

    for v in result:
        out_edges = result.out_edges(v)
        if len(out_edges) > 1:
            raise GraphError('Cluster %s in more than one parent: %s'
                % (v, ', '.join(v for _, v in out_edges)))

    return result


def to_graphviz(facts, style_facts):
    """
    Return a `pygraphviz` graph representing `facts`,
    with mapping specified with `style_facts`.
    """
    styles = FactModel(style_facts)
    styles_by_type = {
        type: {style.name for style in styles}
        for type, styles in group_sorted(styles.object_facts,
                                         attrgetter('type'))}
    node_types = styles_by_type.get('node-type', set())
    cluster_types = styles_by_type.get('cluster-type', set())
    nodelike_types = node_types | cluster_types
    edge_types = styles_by_type.get('edge-type', set())
    containments = styles_by_type.get('containment', set())

    objects = [o for o in facts if 'type' in o]
    relations = [r for r in facts if 'rel' in r]
    clusters = build_clusters(objects, relations, styles_by_type)

    g = gv.AGraph(strict=False, directed=True)
    subgraphs = {}
    for o in objects:
        if o.type in node_types:
            logging.getLogger(__name__).debug(
                'Adding node for %s %s', o.type, o.name)
            g.add_node(o.name, **updated(styles[o.type], o.attrs.asDict()))
        else:
            logging.getLogger(__name__).debug(
                'Skipping object %s %s', o.type, o.name)
    nodes = set(g.nodes())
    vertices = nodes | set(clusters.nodes())
    for i, r in enumerate(relations):
        if (r.rel in edge_types
                and {r.lhs, r.rhs} <= vertices
            or r.rel in containments
                and r.lhs in vertices
                and r.rhs in nodes):
            logging.getLogger(__name__).debug(
                'Adding edge for %s %s %s', r.lhs, r.rel, r.rhs)
            g.add_edge(
                '%s%s' % ('cluster' if r.lhs in clusters else '', r.lhs),
                '%s%s' % ('cluster' if r.rhs in clusters else '', r.rhs),
                key=i,
                **updated(styles[r.rel], r.attrs.asDict(),
                          {key: value
                           for key, value in (('taillabel', r.lhs_label),
                                              ('headlabel', r.rhs_label))
                           if value is not None}))

        logging.getLogger(__name__).debug(
            'Skipping relation %s %s %s', r.lhs, r.rel, r.rhs)
        continue
    for cluster in nx.topological_sort(clusters, reverse=True):
        o = clusters.node[cluster]
        parents = [parent for _, parent in clusters.out_edges([cluster])]
        logging.getLogger(__name__).debug('Adding cluster %s in %s', cluster,
                                          parents[0] if parents else 'root')
        subgraphs[cluster] = (
            (subgraphs[parents[0]] if parents else g)
            .add_subgraph([], name='cluster%s' % cluster,
                          **updated(styles[o['type']], o['attrs'])))
        subgraphs[cluster].add_nodes_from(
            r.lhs for r in relations
            if r.lhs not in clusters
            and r.rel in containments
            and r.rhs == cluster)

    return g


def main():
    args = parse_args()

    logging.basicConfig(stream=sys.stderr, format='%(message)s')
    logging.getLogger(__name__).setLevel(logging.DEBUG if args.verbose
                                         else logging.INFO)

    if args.default_style:
        style_data = load_default_style()
        style_facts = fact_parser.parse(style_data)
    if args.style:
        style_data = args.style.read() + '\n'
        style_facts.extend(fact_parser.parse(style_data))

    fact_data = args.facts.read() + '\n'
    facts = fact_parser.parse(fact_data)

    g = to_graphviz(facts, style_facts)
    g.write(args.output)


if __name__ == '__main__':
    main()
