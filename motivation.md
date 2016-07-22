# Design goals (or, Why not Graphviz)

This language is intended to be a human-readable and writable notation
for directed multigraphs with diverse types of vertices and edges. More
on each point below.


## Refresher: Graphviz syntax

In Graphviz, vertices are specified by simply mentioning a name, and
directed edges by connecting two names with an arrow symbol (`->`).
Additionally, vertices and edges can have attributes, written out
after the vertex or edge in brackets:

```
digraph {
    Base [shape=box]
    Derived [shape=box]
    Derived -> Base [style=dashed, arrowhead=empty]
}
```

There is one shortcut. A set of default attributes can be specified at
any point, and it applies to all subsequent vertices or edges until
the end of graph or until a different default is set.

Another shortcut is that vertices need not be declared. They acquire
default vertex attributes at first mention.

The above definition could alternatively be written like this:

```
digraph {
    node [shape=box]
    Derived -> Base [style=dashed, arrowhead=empty]
}
```


## Directed multigraphs

We want to be able to talk about objects and their relations in order
to visualize models. We want to depict relations as edges in a graph.

Most non-mathematical relations are not symmetric. For example, two
classes in an OOP language cannot inherit from each other. So we want
directed graphs.

Two objects can simultaneously participate in multiple relations. For
example, in a Composite design pattern, a Composite both generalizes
Component and aggregates a number of them. This calls for a
multigraph.

Another feature of a multigraph is that it allows an edge to have the
same vertex at its both ends, which is also handy.


## Diverse types of nodes and edges

We want to express many different types of objects and relations. For
example, in a description of software architecture, we want to speak
about classes, interfaces, packages, components, and nodes; and their
various relations such as association, aggregation, composition,
generalization, containment, dependency, deployment, and more.

The natural way to concisely express all these on a diagram is to use
diverse shapes, colors and line styles. For example, in UML, the
generalization relation between two classes, also known as
inheritance, is depicted as a solid line with a hollow triangle at the
base end, while a dependency is shown as a dashed line with an
arrowhead.

In Graphviz, we have two possibilities:

* spell out all attributes on each edge; or
* group edges so that their common attributes can be set as a local
  default.

The former is tedious. The latter leads to descriptions where a
vertex’s edges can be far removed from the vertex.

To solve this problem, we will use a word (“relation type”) in place
of the arrow, and assign different sets of attributes to different
relation types. We will also allow declaring vertices with an object
type, and also assign a set of attributes to each object type.

```
interface Component
class Leaf
Leaf is-a Component
class Composite
Composite is-a Component
Composite has-many Component
```


## Human-readable

Expressing the type of an object or relation in a diagram involves a
step of encoding. In Graphviz, we perform that when we spell out the
attributes of a vertex or an edge. Reading such a description back
requires decoding.

On the contrary, expressing vertex and edge types with natural
language words preserves readability.


## Human-writable

Suppose we are reading source code and find that the class named
`Composite` inherits from `Component`. We want to document it in our
model.

In Graphviz, we’d have to follow either of the procedures below:

* Type in the edge: `Composite -> Component`.
* Perform the coding in our head: “generalization is depicted as a
  dashed line with a hollow triangle at the end”.
* Type in the attributes: `[style=dashed, arrowhead=empty]`.
  * This may require a roundtrip to Graphviz documentation if we don’t
    exactly remember how attribute names or values are spelled.

or:

* Find the section in the file with the appropriate defaults.
  * If this is the first relation of its type, add a new section:
    `edge [style=dashed, arrowhead=empty]`.
* Type in the edge: `Composite -> Component`.

Both are slow and break flow.

Alternatively, we only have to type: `Composite is-a Component`. The
set of standard relations is expected to be sufficiently compact as to
be internalized so you don’t have to consult documentation.
