"""The first scheme must be creatable from an empty browser session."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import patch

import flet as ft
import pytest

from data.models import AppData
from test_navigation import click_nav, mount, no_client_mount, walk
from test_progressive_memo import letter_scheme


@pytest.mark.parametrize('style', ['top_tabs', 'compact_sidebar', 'popout'])
@pytest.mark.parametrize('width', [1440, 390])
def test_fresh_browser_has_a_visible_creation_form_and_opens_the_saved_scheme(style, width):
    page, repo = mount(style, width=width)
    view = click_nav(page, 'Letter Schemes')
    fields = [c for c in walk(view.body_scroll) if isinstance(c, ft.TextField)]
    assert fields, 'First-time setup needs a creation form in the main area.'
    create = next(c for c in walk(view.body_scroll)
                  if isinstance(c, ft.FilledButton) and c.tooltip == 'Create letter scheme')
    assert view.body_scroll.height > 0 and not view.sidebar.visible
    fields[0].value = '  My first scheme  '
    with patch.object(type(view), 'update'):
        create.on_click(SimpleNamespace(control=create))
    assert repo.data.active_scheme == 'My first scheme'
    assert list(repo.data.schemes) == ['My first scheme']
    assert view._cards_editor is not None and view.sidebar.visible
    assert view.sidebar.height > 0 and view._sticker_fields
    restored = AppData.from_dict(json.loads(json.dumps(repo.data.to_dict())))
    assert restored.active_scheme == 'My first scheme'
    assert restored.schemes['My first scheme'].to_dict() == repo.data.schemes['My first scheme'].to_dict()


@pytest.mark.parametrize('stale_active', ['', 'missing scheme'])
def test_first_scheme_enter_submission_repairs_an_empty_or_stale_active_selection(stale_active):
    page, repo = mount()
    repo.data.active_scheme = stale_active
    view = click_nav(page, 'Letter Schemes')
    field = next(c for c in walk(view.body_scroll) if isinstance(c, ft.TextField))
    field.value = 'New scheme'
    with patch.object(type(view), 'update'):
        field.on_submit(SimpleNamespace(control=field))
    assert repo.data.active_scheme == 'New scheme' and view._cards_editor is not None


def test_sidebar_creation_selects_the_new_scheme_and_preserves_the_previous_one():
    page, repo = mount()
    scheme = letter_scheme()
    repo.data.schemes = {scheme.name: scheme}
    repo.data.active_scheme = scheme.name
    view = click_nav(page, 'Letter Schemes')
    before = deepcopy(scheme.to_dict())
    view.new_scheme_field.value = scheme.name
    with patch.object(type(view), 'update'):
        view._create_scheme(None)
    assert repo.data.active_scheme == scheme.name + ' (2)'
    assert view.state.active_scheme.name == scheme.name + ' (2)'
    assert repo.data.schemes[scheme.name].to_dict() == before
    assert view._cards_editor is not None and view.new_scheme_field.value == ''
