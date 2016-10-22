# encoding=utf-8
# 
# Copyright © 2016 Dylan Baker

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Test module for the _CaseInsenstiveUnicode class."""

from alot.account import _CaseInsensitiveUnicode as CU

import pytest


@pytest.fixture
def inst():
    return CU('fooBar')

@pytest.fixture
def spaced():
    return CU(' fooBar  ')

@pytest.mark.parametrize("value", [
    'foobarx', 'FOOBARX', u'foobarx', u'FOOBARx'])
def test_lt(value, inst):
    assert inst < value

@pytest.mark.parametrize("value", [
    'foobarx', 'FOOBARX', u'foobarx', u'FOOBARx', 'foobarX', 'FOOBARx',
    u'foobarX', u'FOOBARx'])
def test_le(value, inst):
    assert inst <= value

@pytest.mark.parametrize("value", ['foobA', 'FOOBa', u'foobA', u'FOOBa'])
def test_gt(value, inst):
    assert inst > value

@pytest.mark.parametrize("value", [
    'fooba', 'FOOBA', u'fooba', u'FOOBA', 'fooba', 'FOOBA', u'fooba',
    u'FOOBA'])
def test_ge(value, inst):
    assert inst >= value

@pytest.mark.parametrize("value", [
    'foobaR', 'FOOBAr', u'foobaR', u'FOOBAr', 'foobar', 'FOOBAR',
    u'foobar', u'FOOBAR'])
def test_eq(value, inst):
    assert inst == value

def test_contains(inst):
    assert 'foo' in inst

def test_capitalize(inst):
    # Using "is" is the only straightforward way to test this, since most
    # copy methods simply return self
    assert inst.capitalize() is inst

def test_center(inst):
    assert inst.center(12) == '   {}   '.format(inst)

def test_endswith(inst):
    assert inst.endswith('BaR')

def test_expandtabs():
    inst = CU('\tfoo')
    assert inst.expandtabs(2) == '  Foo'

def test_ljust(inst):
    assert inst.ljust(7) == 'foObar '

def test_lower(inst):
    # Using "is" is the only straightforward way to test this, since most
    # copy methods simply return self
    assert inst.lower() is inst

def test_lstrip(spaced):
    assert spaced.lstrip() == 'FoobaR  '

def test_partition(inst):
    assert ('fOo', 'b', 'Ar') == inst.partition('B')

def test_rjust(inst):
    assert inst.rjust(7) == ' foObar'

def test_rsplit(inst):
    assert inst.rsplit(u'b') == ['foo', 'ar']

def test_rstrip(spaced):
    assert spaced.rstrip() == ' FOObar'

def test_split(inst):
    assert inst.rsplit('o') == ['f', '', 'Bar']

def test_splitlines():
    inst = CU('foo\nbar\noink')
    assert inst.splitlines() == ['foO', 'Bar', 'oiNk']

def test_startswith(inst):
    assert inst.startswith('FOo')

def test_swapcase(inst):
    # Using "is" is the only straightforward way to test this, since most
    # copy methods simply return self
    assert inst.swapcase() is inst

def test_title(inst):
    # Using "is" is the only straightforward way to test this, since most
    # copy methods simply return self
    assert inst.title() is inst

def test_upper(inst):
    # Using "is" is the only straightforward way to test this, since most
    # copy methods simply return self
    assert inst.upper() is inst

def test_zfill(inst):
    assert inst.zfill(8) == '00FoobAr'
