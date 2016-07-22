#!/usr/bin/python3
"""
Defines a grammar for parsing fact files.
"""

import logging
import unittest

from pyparsing import (Dict, Group, Literal, OneOrMore, Optional,
                       ParseException, ParseResults, QuotedString, Regex,
                       ZeroOrMore, delimitedList, oneOf, pythonStyleComment,
                       stringEnd)

# The grammar is whitespace-sensitive in the sense that a line break is not
# equivalent to linear whitespace. Therefore, most leaf nonterminals must
# modify their whitespace character set from pyparsing’s default.
#
# Changing the default would solve the local problem by modifying a global
# setting, so we don’t do that.
#
#     from pyparsing import ParserElement
#     ParserElement.setDefaultWhitespaceChars(' \t')

def _lws(expr):
    """
    Return expr modified to skip only linear whitespace.
    """
    return expr.setWhitespaceChars(' \t')

_comment = _lws(pythonStyleComment)
_nl = (Optional(_comment)
       + Optional(Literal('\r').leaveWhitespace()).suppress()
       + Literal('\n').setName('newline').leaveWhitespace()).suppress()
_blank_line = _nl
_string = _lws(QuotedString('"', escChar='\\', unquoteResults=True)
               .setName('quoted string'))
_multiline_string = _lws(QuotedString('"""', escChar='\\', unquoteResults=True,
                                      multiline=True)
                         .setName('multiline string'))
_paren_string = _lws(QuotedString('(', endQuoteChar=')', escChar='\\',
                                  unquoteResults=True, multiline=True)
                     .setName('parenthetical'))

# Rationale for different syntaxes for attribute names:
# We want the colon as the separator between attribute name and value.
# At the same time, we want to be able to use the colon in the names of
# objects and classes without quoting them.
#
# We also want to not have to quote attribute values unless necessary.
#
_name = (_lws(Regex('[^ \t\r\n#",]+'))
         | _multiline_string | _string).setName('name')
_attribute_name = (_lws(Regex('[^ \t\r\n#",:]+'))
                   | _multiline_string | _string).setName('attribute name')
_attribute_value = (_lws(Regex('[^\n#"]*[^\n#" \t]'))
                    | _multiline_string | _string).setName('attribute value')

_indentation = OneOrMore(oneOf([' ', '\t']).leaveWhitespace()).suppress()
_colon = _lws(Literal(':')).suppress()

_attribute = Group(_indentation + _attribute_name + _colon
                   + _attribute_value) + _nl
_attributes = Dict(ZeroOrMore(_attribute | _blank_line))('attrs')

_comma = _lws(Literal(',')).suppress()

def _make_results(*pairs):
    result = ParseResults([value for _key, value in pairs if value is not None])
    for key, value in pairs:
        if value is not None:
            result[key] = value
    return result

def _dump(results):
    if not isinstance(results, ParseResults):
        return results
    if results.haskeys():
        return {key: _dump(value) for key, value in results.asDict().items()}
    return [_dump(item) for item in results]

def _expand_objects(tokens=ParseResults([])):
    results = ParseResults([_make_results(('type', token.type),
                                          ('name', name),
                                          ('attrs', token.attrs))
                            for token in tokens
                            for name in token.names])
    return results

def _expand_relations(tokens=[]):
    return ParseResults([
        _make_results(('lhs', lhs),
                      ('lhs_label', token.get('lhs_label', None)),
                      ('rel', token.rel),
                      ('rhs_label', token.get('rhs_label', None)),
                      ('rhs', rhs),
                      ('attrs', token.attrs))
        for token in tokens
        for lhs in token.lhss
        for rhs in token.rhss])

def _expand_objects_with_relation(tokens=ParseResults([])):
    result_tokens = ([_make_results(('type', token.type),
                       ('name', name),
                       ('attrs', token.attrs))
         for token in tokens
         for name in token.names]
        + [_make_results(('lhs', name),
                         ('lhs_label', token.get('lhs_label', None)),
                         ('rel', token.rel),
                         ('rhs_label', token.get('rhs_label', None)),
                         ('rhs', rhs),
                         ('attrs', ParseResults([])))
           for token in tokens
           for name in token.names
           for rhs in token.rhss])
    results = ParseResults(result_tokens)
    return results

_names = Group(delimitedList(_name, _comma))

_objects = (Group(_name('type')
                  + _names('names')
                  + _nl
                  + _attributes('attrs'))
            .setParseAction(_expand_objects))
_relations = (Group(_names('lhss')
                    + Optional(_paren_string('lhs_label'))
                    + _name('rel')
                    + Optional(_paren_string('rhs_label'))
                    + _names('rhss')
                    + _nl
                    + _attributes('attrs'))
              .setParseAction(_expand_relations))
_objects_with_relation = (
    Group(_name('type') + _names('names')
          + Optional(_paren_string('lhs_label'))
          + _name('rel') + Optional(_paren_string('rhs_label'))
          + _names('rhss') + _nl + _attributes('attrs'))
    .setParseAction(_expand_objects_with_relation))

_fact = _objects | _relations | _objects_with_relation
_source = ZeroOrMore(_fact | _blank_line) + stringEnd

def parse(string, start=_source, parseAll=True):
    """
    Return parsed facts from a string.
    """
    return start.parseString(string, parseAll=parseAll)


class TestCase(unittest.TestCase):
    def assertEqualStruct(self, parsed, expected):
        if isinstance(expected, dict):
            self.assertEqual(set(parsed.keys()), set(expected.keys()))
            for name, value in expected.items():
                self.assertEqualStruct(parsed[name], value)
        elif isinstance(expected, list):
            self.assertEqual(len(parsed), len(expected))
            for parsed_item, expected_item in zip(parsed, expected):
                self.assertEqualStruct(parsed_item, expected_item)
        else:
            self.assertEqual(parsed, expected)


class TestComment(TestCase):
    def test_no_whitespace(self):
        parsed = parse('#comment', _comment)
        self.assertEqualStruct(parsed, ['#comment'])

    def test_linear_whitespace(self):
        parsed = parse('\t  # comment', _comment)
        self.assertEqualStruct(parsed, ['# comment'])

    def test_vertical_whitespace(self):
        with self.assertRaises(ParseException):
            parse('   \n  # comment', _comment)


class TestNewline(TestCase):
    def test_just_nl(self):
        parse('\n', _nl)

    def test_cr_lf(self):
        parse('\r\n', _nl)

    def test_linear_whitespace(self):
        parse('   \t   \n', _nl)

    def test_comment(self):
        parse('#comment\n', _nl)

    def test_lws_comment(self):
        parse('  \t  #comment\n', _nl)

    def test_vertical_whitespace(self):
        with self.assertRaises(ParseException):
            parse('\n#comment\n', _nl)


class TestString(TestCase):
    def test_simple_string(self):
        parsed = parse('"Hello World!"', _string)
        self.assertEqualStruct(parsed, ['Hello World!'])

    def test_embedded_quotes(self):
        parsed = parse(r'"some \"quoted\" words"', _string)
        self.assertEqualStruct(parsed, ['some "quoted" words'])

    def test_embedded_backslash(self):
        parsed = parse(r'"foo\\bar"', _string)
        self.assertEqualStruct(parsed, [r'foo\bar'])

    def test_multiline(self):
        with self.assertRaises(ParseException):
            parse('"hello\nworld"', _string)

    def test_unquoted(self):
        with self.assertRaises(ParseException):
            parse('hello', _string)


class TestMultilineString(TestCase):
    def test_simple_string(self):
        parsed = parse('"""Hello World!"""', _multiline_string)
        self.assertEqualStruct(parsed, ['Hello World!'])

    def test_embedded_quotes(self):
        parsed = parse(r'"""some "quoted" words"""', _multiline_string)
        self.assertEqualStruct(parsed, ['some "quoted" words'])

    def test_embedded_backslash(self):
        parsed = parse(r'"""foo\\bar"""', _multiline_string)
        self.assertEqualStruct(parsed, [r'foo\bar'])

    def test_multiline(self):
        parsed = parse('"""hello\nworld"""', _multiline_string)
        self.assertEqualStruct(parsed, ['hello\nworld'])

    def test_unquoted(self):
        with self.assertRaises(ParseException):
            parse('hello', _multiline_string)


class TestParenString(TestCase):
    def test_simple_string(self):
        parsed = parse('(Hello World!)', _paren_string)
        self.assertEqualStruct(parsed, ['Hello World!'])

    def test_embedded_parens(self):
        parsed = parse(r'(some \(parenthesized\) words)', _paren_string)
        self.assertEqualStruct(parsed, ['some (parenthesized) words'])

    def test_embedded_backslash(self):
        parsed = parse(r'(foo\\bar)', _paren_string)
        self.assertEqualStruct(parsed, [r'foo\bar'])

    def test_multiline(self):
        parsed = parse('(hello\nworld)', _paren_string)
        self.assertEqualStruct(parsed, ['hello\nworld'])

    def test_unquoted(self):
        with self.assertRaises(ParseException):
            parse('hello', _paren_string)


class TestName(TestCase):
    def test_word(self):
        for nt in ('_name', '_attribute_name'):
            with self.subTest(nt=nt):
                parsed = parse('hello', globals()[nt])
                self.assertEqualStruct(parsed, ['hello'])

    def test_colon(self):
        with self.subTest(nt='_name'):
            parsed = parse('hello:world', _name)
            self.assertEqualStruct(parsed, ['hello:world'])
        with self.subTest(nt='_attribute_name'):
            with self.assertRaises(ParseException):
                parse('hello:world', _attribute_name)

    def test_unquoted(self):
        for nt in ('_name', '_attribute_name'):
            with self.subTest(nt=nt):
                with self.assertRaises(ParseException):
                    parse('hello world', globals()[nt])

    def test_single_quoted(self):
        for nt in ('_name', '_attribute_name'):
            with self.subTest(nt=nt):
                parsed = parse('"hello world"', globals()[nt])
                self.assertEqualStruct(parsed, ['hello world'])

    def test_single_quoted_multiline(self):
        for nt in ('_name', '_attribute_name'):
            with self.subTest(nt=nt):
                with self.assertRaises(ParseException):
                    parse('"hello\nworld"', globals()[nt])

    def test_triple_quoted(self):
        for nt in ('_name', '_attribute_name'):
            with self.subTest(nt=nt):
                parsed = parse('"""hello world"""', globals()[nt])
                self.assertEqualStruct(parsed, ['hello world'])

    def test_triple_quoted_multiline(self):
        for nt in ('_name', '_attribute_name'):
            with self.subTest(nt=nt):
                parsed = parse('"""hello\nworld"""', globals()[nt])
                self.assertEqualStruct(parsed, ['hello\nworld'])


class TestAttribute(TestCase):
    def test_correct(self):
        parsed = parse('  hello: world\n', _attribute)
        self.assertEqualStruct(parsed, [['hello', 'world']])

    def test_unindented(self):
        with self.assertRaises(ParseException):
            parse('hello: world\n', _attribute)

    def test_no_colon(self):
        with self.assertRaises(ParseException):
            parse('  hello world\n', _attribute)

    def test_many_colons(self):
        parsed = parse('  hello: brave: new world\n', _attribute)
        self.assertEqualStruct(parsed, [['hello', 'brave: new world']])

    def test_quoted_value(self):
        parsed = parse('  hello: "brave new world"\n', _attribute)
        self.assertEqualStruct(parsed, [['hello', 'brave new world']])

    def test_comment(self):
        parsed = parse('  hello: world# comment\n', _attribute)
        self.assertEqualStruct(parsed, [['hello', 'world']])

    def test_lws_comment(self):
        parsed = parse('  hello: this world   # comment\n', _attribute)
        self.assertEqualStruct(parsed, [['hello', 'this world']])


class TestAttributes(TestCase):
    def test_empty(self):
        parsed = parse('', _attributes)
        self.assertEqualStruct(parsed, {'attrs': {}})

    def test_correct(self):
        parsed = parse('  fontname: "Liberation Sans"\n'
                       '  fontsize: 10 # comment\n'
                       '  # more comment\n'
                       '  fontweight: bold\n', _attributes)
        self.assertEqualStruct(parsed, {'attrs': {
            'fontname': 'Liberation Sans',
            'fontsize': '10',
            'fontweight': 'bold'}})

    def test_unindented(self):
        with self.assertRaises(ParseException):
            parse('person John\n', _attributes)


class TestDelimitedList(TestCase):
    def test_correct(self):
        parsed = delimitedList(_name, _comma).parseString(
            'foo, bar, baz', parseAll=True)
        self.assertEqualStruct(parsed, ['foo', 'bar', 'baz'])

    def test_multiline(self):
        with self.assertRaises(ParseException):
            delimitedList(_name, _comma).parseString('foo,\nbar', parseAll=True)


class TestObjects(TestCase):
    def test_single_object_no_attrs(self):
        parsed = parse('person John\n', _objects)
        self.assertEqualStruct(parsed, [{'type': 'person', 'name': 'John',
                                         'attrs': {}}])

    def test_single_object_with_attrs(self):
        parsed = parse('person John\n'
                       '  age: 36\n', _objects)
        self.assertEqualStruct(parsed, [{'type': 'person', 'name': 'John',
                                         'attrs': {'age': '36'}}])

    def test_multiple_objects(self):
        # It is surprisingly difficult to come up with a good example of
        # multiple objects of the same type having the same set of attributes.
        # So, an artificial example.
        parsed = parse('animal cat, dog\n'
                       '  n_paws: 4\n', _objects)
        self.assertEqualStruct(parsed, [
            {'type': 'animal', 'name': 'cat', 'attrs': {'n_paws': '4'}},
            {'type': 'animal', 'name': 'dog', 'attrs': {'n_paws': '4'}}])

    def test_relation(self):
        with self.assertRaises(ParseException):
            parse('John works-at AcmeCorp\n', _objects)


class TestRelations(TestCase):
    def test_object(self):
        with self.assertRaises(ParseException):
            parse('person John\n', _relations)

    def test_single_relation_no_attrs(self):
        parsed = parse('John works-at AcmeCorp\n', _relations)
        self.assertEqualStruct(parsed, [{'lhs': 'John', 'rhs': 'AcmeCorp',
                                         'rel': 'works-at', 'attrs': {}}])

    def test_single_relation_with_attrs(self):
        parsed = parse('John works-at AcmeCorp\n'
                       '  salary: 100500\n', _relations)
        self.assertEqualStruct(parsed, [{'lhs': 'John', 'rhs': 'AcmeCorp',
                                         'rel': 'works-at',
                                         'attrs': {'salary': '100500'}}])

    def test_single_relation_with_labels_and_attrs(self):
        parsed = parse('John (employee) works-at (employer) AcmeCorp\n'
                       '  salary: 100500\n', _relations)
        self.assertEqualStruct(parsed, [{
            'lhs': 'John', 'lhs_label': 'employee',
            'rhs': 'AcmeCorp', 'rhs_label': 'employer',
            'rel': 'works-at', 'attrs': {'salary': '100500'}}])

    def test_multiple_lhs_relation(self):
        parsed = parse('Jack, Mary works-at AcmeCorp\n'
                       '  position: accountant\n', _relations)
        self.assertEqualStruct(parsed, [
            {'lhs': 'Jack', 'rhs': 'AcmeCorp', 'rel': 'works-at',
             'attrs': {'position': 'accountant'}},
            {'lhs': 'Mary', 'rhs': 'AcmeCorp', 'rel': 'works-at',
             'attrs': {'position': 'accountant'}}])

    def test_multiple_rhs_relation(self):
        parsed = parse('Stan works-at AcmeCorp, "Some startup"\n'
                       '  position: sysadmin\n', _relations)
        self.assertEqualStruct(parsed, [
            {'lhs': 'Stan', 'rhs': 'AcmeCorp', 'rel': 'works-at',
             'attrs': {'position': 'sysadmin'}},
            {'lhs': 'Stan', 'rhs': 'Some startup', 'rel': 'works-at',
             'attrs': {'position': 'sysadmin'}}])


class TestObjectsWithRelation(TestCase):
    def test_single(self):
        parsed = parse('class Derived is-a Base\n'
                       '  size: 32\n', _objects_with_relation)
        self.assertEqualStruct(parsed, [
            {'type': 'class', 'name': 'Derived', 'attrs': {'size': '32'}},
            {'lhs': 'Derived', 'rhs': 'Base', 'rel': 'is-a', 'attrs': {}}])

    def test_labels(self):
        parsed = parse('class Derived (child) is-a (parent) Base\n'
                       '  size: 32\n', _objects_with_relation)
        self.assertEqualStruct(parsed, [
            {'type': 'class', 'name': 'Derived',
             'attrs': {'size': '32'}},
            {'lhs': 'Derived', 'lhs_label': 'child',
             'rhs': 'Base', 'rhs_label': 'parent', 'rel': 'is-a', 'attrs': {}}])

    def test_multiple(self):
        # Again, not sure if this is useful
        parsed = parse('class Derived1, Derived2 is-a Base1, Base2\n'
                       '  size: 32\n', _objects_with_relation)
        self.assertEqualStruct(parsed, [
            {'type': 'class', 'name': 'Derived1', 'attrs': {'size': '32'}},
            {'type': 'class', 'name': 'Derived2', 'attrs': {'size': '32'}},
            {'lhs': 'Derived1', 'rhs': 'Base1', 'rel': 'is-a', 'attrs': {}},
            {'lhs': 'Derived1', 'rhs': 'Base2', 'rel': 'is-a', 'attrs': {}},
            {'lhs': 'Derived2', 'rhs': 'Base1', 'rel': 'is-a', 'attrs': {}},
            {'lhs': 'Derived2', 'rhs': 'Base2', 'rel': 'is-a', 'attrs': {}}])


class TestFact(TestCase):
    def test_object(self):
        parsed = parse('person John\n'
                       '  age: 36\n', _fact)
        self.assertEqualStruct(parsed, [{'type': 'person', 'name': 'John',
                                         'attrs': {'age': '36'}}])

    def test_relation(self):
        parsed = parse('John works-at AcmeCorp\n', _fact)
        self.assertEqualStruct(parsed, [{'lhs': 'John', 'rhs': 'AcmeCorp',
                                         'rel': 'works-at', 'attrs': {}}])

    def test_relation_attrs(self):
        parsed = parse('John works-at AcmeCorp\n'
                       '  position: senior dev\n'
                       '  salary: 100500\n', _fact)
        self.assertEqualStruct(parsed, [
            {'lhs': 'John', 'rhs': 'AcmeCorp', 'rel': 'works-at',
             'attrs': {'position': 'senior dev', 'salary': '100500'}}])

    def test_object_with_relation(self):
        parsed = parse('class Derived is-a Base\n'
                       '  size: 32\n', _fact)
        self.assertEqualStruct(parsed, [
            {'type': 'class', 'name': 'Derived', 'attrs': {'size': '32'}},
            {'lhs': 'Derived', 'rhs': 'Base', 'rel': 'is-a', 'attrs': {}}])


class TestSource(TestCase):
    def test_full(self):
        parsed = parse(
            '# whole-line comment\n'
            'person John\n'
            '  age: 36 # line-end comment\n'
            '\n'
            'company "Acme Corporation", "Some Startup"\n'
            'John (senior dev) works-at (day job) "Acme Corporation"\n'
            '  salary: 100500\n'
            'John (CEO) works-at (personal project) "Some Startup"\n'
            '  salary: 0\n')
        self.assertEqualStruct(parsed, [
            {'name': 'John', 'type': 'person', 'attrs': {'age': '36'}},
            {'type': 'company', 'name': 'Acme Corporation', 'attrs': {}},
            {'type': 'company', 'name': 'Some Startup', 'attrs': {}},
            {'lhs': 'John', 'lhs_label': 'senior dev',
             'rhs': 'Acme Corporation', 'rhs_label': 'day job',
             'rel': 'works-at', 'attrs': {'salary': '100500'}},
            {'lhs': 'John', 'lhs_label': 'CEO',
             'rhs': 'Some Startup', 'rhs_label': 'personal project',
             'rel': 'works-at', 'attrs': {'salary': '0'}}])

if __name__ == '__main__':
    logging.basicConfig(format='%(message)s')
    logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()
