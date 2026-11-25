"""Front-end tests: template helpers, rendered markup, accessibility basics and static assets."""
import re
from collections import Counter
from html.parser import HTMLParser

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.template import Context, Template
from django.test import TestCase
from django.urls import reverse

from .models import Favorite, Room, Student, Tutor
from .templatetags.ui import avatar_hue, initials

User = get_user_model()
PUBLIC_PAGES = ['home', 'catalog', 'login', 'register', 'offline']
SIGNED_IN_PAGES = ['dashboard', 'my_bookings', 'favorites', 'notifications', 'profile']


class Page(HTMLParser):
    """Collects the bits of a rendered page the tests care about."""

    def __init__(self, html):
        super().__init__()
        self.h1 = 0
        self.ids = []
        self.imgs = []
        self.blank_links = []
        self.mains = 0
        self.root_lang = None
        self.buttons_without_type = []
        self.forms = []
        self._form = None
        self.skip_target = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.append(a['id'])
        if tag == 'html':
            self.root_lang = a.get('lang')
        elif tag == 'h1':
            self.h1 += 1
        elif tag == 'main':
            self.mains += 1
        elif tag == 'img':
            self.imgs.append(a)
        elif tag == 'a':
            if a.get('target') == '_blank':
                self.blank_links.append(a)
            if 'skip-link' in (a.get('class') or ''):
                self.skip_target = a.get('href')
        elif tag == 'button' and 'type' not in a:
            self.buttons_without_type.append(a)
        elif tag == 'form':
            self._form = {'method': (a.get('method') or 'get').lower(), 'csrf': False}
            self.forms.append(self._form)
        elif tag == 'input' and self._form is not None and a.get('name') == 'csrfmiddlewaretoken':
            self._form['csrf'] = True

    def handle_endtag(self, tag):
        if tag == 'form':
            self._form = None


def render(template, **ctx):
    return Template('{% load ui %}' + template).render(Context(ctx))


class InitialsFilterTests(TestCase):
    def test_titles_are_skipped(self):
        self.assertEqual(initials('Dr. Aznam Yacoub'), 'AY')
        self.assertEqual(initials('Prof. Ziad Kobti'), 'ZK')

    def test_single_word_and_hyphenated_names(self):
        self.assertEqual(initials('Kobti'), 'K')
        self.assertEqual(initials('Jean-Luc Picard'), 'JP')

    def test_only_first_and_last_word_are_used(self):
        self.assertEqual(initials('Rajbeer Kaur Dutta'), 'RD')

    def test_a_title_on_its_own_is_kept(self):
        self.assertEqual(initials('Dr.'), 'D')

    def test_empty_and_symbol_values_use_the_fallback(self):
        self.assertEqual(initials(''), '?')
        self.assertEqual(initials(None, 'S'), 'S')
        self.assertEqual(initials('123 456'), '?')

    def test_accepts_model_instances_via_str(self):
        self.assertEqual(initials(Tutor(display_name='Dr. Olena Syrotkina', subjects='x')), 'OS')

    def test_output_is_upper_case_and_never_longer_than_two_letters(self):
        for name in ('ada lovelace', 'a b c d e', 'élodie martin'):
            out = initials(name)
            self.assertLessEqual(len(out), 2)
            self.assertEqual(out, out.upper())

    def test_hue_is_stable_in_range_and_case_insensitive(self):
        self.assertEqual(avatar_hue('Dr. Aznam Yacoub'), avatar_hue('  dr. aznam yacoub '))
        for name in ('a', 'Dr. Ziad Kobti', '', None):
            self.assertTrue(0 <= avatar_hue(name) < 360)
        self.assertNotEqual(avatar_hue('Dr. Ziad Kobti'), avatar_hue('Dr. Aznam Yacoub'))

    def test_filters_work_inside_a_template(self):
        self.assertEqual(render('{{ n|initials }}', n='Dr. Boufama').strip(), 'B')


class AvatarRenderingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('stu@example.test', 'stu@example.test', 'GoodPassword123!',
                                            first_name='Vrajkumar', last_name='Patel')
        cls.student = Student.objects.create(user=cls.user)
        cls.tutor = Tutor.objects.create(display_name='Dr. Aznam Yacoub', subjects='Cognitive Modelling', title='Professor')
        cls.room = Room.objects.create(name='Group Study Room 318A', building='Leddy Library', capacity=4)

    def test_saved_for_later_shows_initials_not_the_whole_name(self):
        """Regression: the dashboard avatar used to print the full name and overflow its circle."""
        Favorite.objects.create(student=self.student, tutor=self.tutor)
        self.client.force_login(self.user)
        html = self.client.get(reverse('dashboard')).content.decode()
        self.assertRegex(html, r'<span class="avatar avatar-sm"[^>]*>AY</span>')
        self.assertNotRegex(html, r'<span class="avatar[^>]*>\s*Dr\. Aznam Yacoub\s*</span>')

    def test_saved_room_uses_the_building_glyph(self):
        Favorite.objects.create(student=self.student, room=self.room)
        self.client.force_login(self.user)
        html = self.client.get(reverse('dashboard')).content.decode()
        self.assertIn('avatar avatar-sm avatar-square room-glyph', html)
        self.assertNotRegex(html, r'<span class="avatar[^>]*>\s*Group Study Room 318A\s*</span>')

    def test_tutor_card_avatar_is_decorative_with_initials_and_colour(self):
        html = self.client.get(reverse('catalog')).content.decode()
        self.assertRegex(html, r'<span class="avatar avatar-lg" style="--h: \d+" aria-hidden="true">AY</span>')

    def test_profile_page_avatar_and_navigation_avatar_use_the_full_name(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse('profile')).content.decode()
        self.assertIn('>VP</span>', html)

    def test_every_avatar_text_is_at_most_two_characters(self):
        Favorite.objects.create(student=self.student, tutor=self.tutor)
        self.client.force_login(self.user)
        for name in ('dashboard', 'catalog', 'favorites', 'profile'):
            html = self.client.get(reverse(name)).content.decode()
            for text in re.findall(r'<span class="avatar(?![^"]*room-glyph)[^"]*"[^>]*>([^<]*)</span>', html):
                self.assertLessEqual(len(text.strip()), 2, (name, text))


class MarkupQualityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('q@example.test', 'q@example.test', 'GoodPassword123!', first_name='Quinn')
        cls.student = Student.objects.create(user=cls.user)
        cls.tutor = Tutor.objects.create(
            display_name='Dr. Example', subjects='Databases', title='Professor', office='5103',
            research_interests='Pattern mining; Recommendation systems', profile_url='https://www.uwindsor.ca/x')
        cls.room = Room.objects.create(name='Room 1', building='Leddy Library', capacity=4,
                                       info_url='https://leddy.uwindsor.ca/a', rules_url='https://leddy.uwindsor.ca/b')

    def pages(self):
        for name in PUBLIC_PAGES:
            yield name, self.client.get(reverse(name)).content.decode()
        yield 'tutor_detail', self.client.get(reverse('tutor_detail', args=[self.tutor.pk])).content.decode()
        yield 'room_detail', self.client.get(reverse('room_detail', args=[self.room.pk])).content.decode()
        self.client.force_login(self.user)
        for name in SIGNED_IN_PAGES:
            yield name, self.client.get(reverse(name)).content.decode()

    def test_every_page_renders(self):
        for name in PUBLIC_PAGES:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.client.force_login(self.user)
        for name in SIGNED_IN_PAGES:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_landmarks_language_and_skip_link(self):
        for name, html in self.pages():
            if name == 'offline':
                continue
            page = Page(html)
            self.assertEqual(page.root_lang, 'en', name)
            self.assertEqual(page.mains, 1, name)
            self.assertEqual(page.skip_target, '#main-content', name)
            self.assertIn('id="main-content"', html, name)

    def test_exactly_one_h1_per_page(self):
        for name, html in self.pages():
            self.assertEqual(Page(html).h1, 1, f'{name} should have a single <h1>')

    def test_ids_are_unique_on_every_page(self):
        for name, html in self.pages():
            dupes = [i for i, n in Counter(Page(html).ids).items() if n > 1]
            self.assertEqual(dupes, [], f'duplicate ids on {name}')

    def test_images_have_alt_text(self):
        for name, html in self.pages():
            for img in Page(html).imgs:
                self.assertIn('alt', img, f'<img> without alt on {name}: {img}')

    def test_new_tab_links_are_safe(self):
        for name, html in self.pages():
            for a in Page(html).blank_links:
                self.assertIn('noopener', a.get('rel', ''), f'{name}: {a.get("href")}')

    def test_post_forms_carry_csrf_tokens(self):
        for name, html in self.pages():
            for form in Page(html).forms:
                if form['method'] == 'post':
                    self.assertTrue(form['csrf'], f'POST form without CSRF token on {name}')

    def test_buttons_declare_a_type(self):
        for name, html in self.pages():
            self.assertEqual(Page(html).buttons_without_type, [], name)

    def test_icon_only_controls_are_labelled(self):
        for name, html in self.pages():
            for tag in re.findall(r'<button[^>]*class="[^"]*(?:fav-btn|bell|nav-burger|toast-close)[^"]*"[^>]*>', html):
                self.assertIn('aria-label', tag, f'{name}: {tag[:80]}')

    def test_head_is_complete_and_scripts_are_deferred(self):
        html = self.client.get(reverse('home')).content.decode()
        for needle in ('<meta name="viewport"', '<title>', 'rel="stylesheet"', 'theme-color'):
            self.assertIn(needle, html)
        for tag in re.findall(r'<script[^>]*src=[^>]*>', html):
            if 'theme-init' not in tag:
                self.assertIn('defer', tag)

    def test_theme_attribute_is_set_before_first_paint(self):
        self.assertIn('theme-init.js', self.client.get(reverse('home')).content.decode())

    def test_csp_allows_the_avatar_colour_variable(self):
        """Avatars colour themselves with an inline style, which the CSP must continue to allow."""
        resp = self.client.get(reverse('catalog'))
        self.assertIn("style-src 'self' 'unsafe-inline'", resp['Content-Security-Policy'])


class StaticAssetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.css = open(finders.find('core/css/style.css'), encoding='utf-8').read()

    def test_assets_are_found_by_staticfiles(self):
        for path in ('core/css/style.css', 'core/js/main.js', 'core/js/theme-init.js'):
            self.assertIsNotNone(finders.find(path), path)

    def test_css_braces_are_balanced(self):
        stripped = re.sub(r'/\*.*?\*/', '', self.css, flags=re.S)
        self.assertEqual(stripped.count('{'), stripped.count('}'))

    def test_css_has_accessibility_media_queries(self):
        for query in ('prefers-reduced-motion', 'prefers-contrast', 'forced-colors', 'prefers-reduced-transparency', 'print'):
            self.assertIn(query, self.css)

    def test_focus_is_visible_for_keyboard_users(self):
        self.assertIn(':focus-visible', self.css)

    def test_avatar_initials_cannot_overflow_the_circle(self):
        block = re.search(r'\.avatar \{ overflow: hidden;[^}]*\}', self.css)
        self.assertIsNotNone(block, 'avatar overflow guard is missing')
        self.assertIn('line-height: 1', block.group(0))

    def test_avatar_sizes_stay_defined(self):
        for size in ('avatar-sm', 'avatar-lg', 'avatar-xl'):
            self.assertRegex(self.css, rf'\.{size} \{{')

    def test_every_icon_used_in_templates_exists(self):
        from pathlib import Path
        root = Path(finders.find('core/css/style.css')).parents[2].parent / 'templates' / 'core'
        icons = (root / '_icon.html').read_text(encoding='utf-8')
        used = set()
        for f in root.glob('*.html'):
            used |= set(re.findall(r"_icon\.html' with name='([\w-]+)'", f.read_text(encoding='utf-8')))
        missing = {n for n in used if f"'{n}'" not in icons and f'"{n}"' not in icons}
        self.assertEqual(missing, set())

    def test_javascript_has_no_debug_leftovers(self):
        js = open(finders.find('core/js/main.js'), encoding='utf-8').read()
        self.assertNotIn('console.log', js)
        self.assertNotIn('debugger', js)
