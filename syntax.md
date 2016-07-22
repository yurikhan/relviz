# Language syntax

## General

Fact files are expected to be text files in the encoding of your locale.

The syntax is line-based, with lines terminated by a single line feed
character (U+000A LINE FEED), optionally preceded by a carriage return
character (U+000D CARRIAGE RETURN). The last line in a source file is
allowed to be unterminated.

Line end comments are supported. A comment starts with a hash
character (`#`, U+0023 NUMBER SIGN) and runs until the end of line.

No line splicing/folding mechanism is provided.

Empty lines are allowed and ignored, as are lines consisting entirely
of whitespace and/or comments.

Tokens are separated with linear whitespace, which is defined here as
one or more consecutive spaces (U+0020 SPACE) or tabs (U+0009
CHARACTER TABULATION).

## Identifiers

Identifiers can be written in any of the following three forms:

* Unquoted word: a sequence of non-whitespace characters, with an
  additional exception of `#` U+0023 NUMBER SIGN (line-end comment
  delimiter), `"` U+0022 QUOTATION MARK (see below), and `,` U+002C
  COMMA (name list delimiter).

* Quoted string: a sequence of any characters except U+000A LINE FEED,
  enclosed in `"` U+0022 QUOTATION MARK characters. To include a
  literal quotation mark character in a quoted string, precede it with
  a `\` U+005C BACKSLASH character. To include a literal backslash
  character, double it.

* Multiline string: a sequence of any characters, including U+000A
  LINE FEED, enclosed in triple `"` U+0022 QUOTATION MARK characters.
  Backslash still has its escaping power, although it is expected to
  be rarely used in this form.

Examples of valid identifiers:

    hello-world

    "Hello World"

    "Hello \"quoted\" world"

    """Hello "quoted"
    multiline world"""

The format in which an identifier is written is not itself
identifying.

## Facts

A source file consists of a sequence of *facts*.

Each fact describes one or more objects and/or relations between one
or more pairs of objects.

### Objects

An object fact has the syntax:

    <type> <name>[, <name>…] [(<label>)]
        [<attributes>]

This establishes that each named object has the specified type, label
and attributes.

`<type>` and `<name>` are identifiers. An optional freeform text
`<label>` can be specified in parentheses `()` U+0028 LEFT
PARENTHESIS, U+0029 RIGHT PARENTHESIS. To include a literal
parenthesis or backslash, precede it with a backslash.

Optionally, an attribute block can follow. The attribute block is a
key-value data structure, where both keys and values are text strings.
The syntax for an attribute block is:

    <indentation><attr-name>: <attr-value>
    …

Every attribute must be indented; the next unindented line starts a
new fact.

An `<attr-name>` follows almost the same syntax as an identifier, with
the exception that its unquoted form cannot contain a `:` U+003A COLON
character.

An `<attr-value>` has similar syntax, but its unquoted form is more
permissive. An unquoted attribute value can contain any characters
except line feed, `#` number sign or `"` quotation mark, and its
trailing whitespace is ignored.

If multiple `<name>`s are specified, the `<type>`, `<label>` and
`<attributes>` apply to each of them.

If a single `<name>` is used in more than one object fact, the
behavior is unspecified.


## Relations

A relation fact looks like this:

    <lhs>[, <lhs>…] [(<label>)] <relation> [(<label>)] <rhs>[, <rhs>…]
        [<attributes>]

This establishes that each named left-hand-side object participates in
the named relation with each named right-hand-side object, and that
these relations have specified labels and attributes.

`<lhs>`, `<relation>` and `<rhs>` have identifier syntax. `<label>`s
are parenthesized strings; one label applies to the left-hand-side end
of the relation, and the other to the right-hand-side end.
