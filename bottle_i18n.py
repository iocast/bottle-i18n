import gettext, os, re
from bottle import PluginError


def i18n_defaults(template, request):
    template.defaults['_'] = lambda msgid: request.app._(msgid)
    template.defaults['lang'] = lambda: request.app.lang


class I18NMiddleware(object):
    
    @property
    def header(self):
        return self._header
    @property
    def http_accept_language(self):
        return self.header.get('HTTP_ACCEPT_LANGUAGE')
    
    def __init__(self, app, i18n, sub_app=True):
        self.app = app
        self.app.install(i18n)
        self._http_language = ""
        i18n.middleware = self
        
        if sub_app:
            for route in self.app.routes:
                if route.config.get('mountpoint'):
                    route.config.get('mountpoint').get('target').install(i18n)
    
    
    def __call__(self, e, h):
        self._http_language = e.get('HTTP_ACCEPT_LANGUAGE')
        self._header = e
        locale = e['PATH_INFO'].split('/')[1]
        for i18n in [plugin for plugin in self.app.plugins if plugin.name == 'i18n']:
            if locale in i18n.locales:
                self.app.lang = locale
                e['PATH_INFO'] = e['PATH_INFO'][len(locale)+1:]
        return self.app(e,h)


class I18NPlugin(object):
    name = 'i18n'
    api = 2
    
    @property
    def middleware(self):
        return self._middleware
    @middleware.setter
    def middleware(self, middleware):
        self._middleware = middleware
    
    def __init__(self, domain, locale_dir=None, lang_code=None, default=None, keyword='i18n'):
        self.domain = domain
        if locale_dir is None:
            locale_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../locale'))
        if not os.path.exists(locale_dir):
            raise PluginError('No locale directory found, please assign a right one.')
        self.locale_dir = locale_dir
        
        self.locales = self._get_languages(self.locale_dir)
        self.default = default
        self.lang_code = lang_code
        
        self.cache = {}
        self.apps = []
        self.keyword = keyword
    
    def _get_languages(self, directory):
        return [dir for dir in os.listdir(self.locale_dir) if os.path.isdir(os.path.join(directory, dir))]
    
    
    def setup(self, app):
        self.apps.append(app)
        for app in self.apps:
            app._ = lambda s: s
            app.hooks.add('before_request', self.prepare)
            
            app.__class__.lang = property(fget=lambda x: self.get_lang(), fset=lambda x, value: self.set_lang(value))
    
    def parse_accept_language(self, accept_language):
        languages = accept_language.split(",")
        locale_q_pairs = []
        
        for language in languages:
            if language.split(";")[0] == language:
                # no q => q = 1
                locale_q_pairs.append((language.strip(), "1"))
            else:
                locale = language.split(";")[0].strip()
                q = language.split(";")[1].split("=")[1]
                locale_q_pairs.append((locale, q))
        
        return locale_q_pairs
    
    
    def detect_locale(self):
        locale_q_pairs = self.parse_accept_language(self.middleware.http_accept_language)
        for pair in locale_q_pairs:
            for locale in self.locales:
                if pair[0].replace('-', '_').lower().startswith(locale.lower()):
                    return locale
        
        return self.default
    
    
    def get_lang(self):
        return self.lang_code
    
    def set_lang(self, lang_code=None):
        self.lang_code = lang_code
        if self.lang_code is None:
            self.lang_code = self.detect_locale()
        
        self.prepare()
    
    def prepare(self, *args, **kwargs):
        if self.lang_code is None:
            self.lang_code = self.detect_locale()
        
        if self.lang_code in self.cache.keys():
            trans = self.cache[self.lang_code]
            if trans:
                trans.install()
                for app in self.apps:
                    app._ = trans.gettext
            else:
                for app in self.apps:
                    app._ = lambda s: s
            return
        try:
            trans = gettext.translation(self.domain, self.locale_dir, languages=[self.lang_code])
            trans.install()
            for app in self.apps:
                app._ = trans.gettext
            self.cache[self.lang_code] = trans
        except Exception, e:
            for app in self.apps:
                app._ = lambda s: s
            self.cache[self.lang_code] = None
    
    
    def apply(self, callback, route):
        return callback
