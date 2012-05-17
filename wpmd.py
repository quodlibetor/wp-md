#!/usr/bin/env python

# wp-md, copyright Brandon W Maister <quodlibetor@gmail.com>
# Free to use under the MIT license: http://mit-license.org/
# Homepage: https://github.com/quodlibetor/wp-md

"""Convert WordPress data from xml into Markdown files.

The main work in here is done by the Exporter class, which does all the work
in its ``__init__`` method, which functions as a dispatcher. Create a class
with the correct arguments and it will do the work, see ``main()`` if you're
curious.

The ``HtmlPreProcessor`` class is a stupidly simple HTML->Markdown converter.
It only converts tags that don't require state-tracking/recursion, and it
doesn't do all of those. What it *does* do, though, is correctly extract
`lang` attributes for syntax-highlighted code blocks, something that I don't
think any of the other html->md converters do.

It's used by by the ``_markdownify`` utility method in ``Exporter``, you
probably don't need to deal with it yourself.
"""
import sys
import os
import re
import argparse
from collections import OrderedDict, defaultdict
from HTMLParser import HTMLParser
try:
    from xml.etree import cElementTree as ET
except ImportError:
    from xml.etree import ElementTree as ET

VERSION = '0.1'

class HtmlPreProcessor(HTMLParser):
    """Replaces <pre> tags with markdown code blocks

    Pass in the html with `feed`, and read out the markdownified junk with
    `readmd()`.

    This class expects *invalid* HTML: the html fragments stored by WordPress
    in the database, with double-newlines instead of <p> tags, and no actual
    <html> or <body> elements.

    This class takes advantage of the fact that HTML is actually valid
    markdown, and does't do much processing, letting `handle_data` just store
    more or less everything that we get.
    """
    def __init__(self, markdown_interpreter='misaka'):
        HTMLParser.__init__(self)
        self.buffer = ""
        self.in_pre = False
        self.end_whitespace = re.compile(r'[ \t\n]\Z')
        self.md_interpreter = markdown_interpreter

    def reset(self):
        HTMLParser.reset(self)
        self.buffer = ""
        self.in_pre = False

    def readmd(self):
        return re.sub(r'\n\n\n+', '\n\n', self.buffer)

    def handle_data(self, data):
        """Put all of the processed data into a buffer

        While this class doesn't actually do much processing, this is where
        the result of it goes.
        """
        self.buffer += data

    def append_endtag(self, end):
        """Append a markdown end tag to the buffer.

        Markdown is much more sensitive to whitespace than html is, so we
        have to be careful.
        """
        end_white = self.end_whitespace.search(self.buffer)
        self.buffer = self.buffer.rstrip()

        # only append the end tag if there is something inside of it
        if self.buffer.endswith(end):
            self.buffer = self.buffer.rstrip(end)
        else:
            self.buffer += end

        if end_white:
            self.buffer += end_white.group(0)

    def handle_entityref(self, name):
        entity = "&%s;" % name
        if self.in_pre:
            self.handle_data(entity)
        else:
            self.handle_data(self.unescape(entity))

    def handle_starttag(self, tag, attrs):
        if tag == 'pre':
            self.in_pre = True
            for attr in attrs:
                if attr[0].lower() == 'lang':
                    # pygments keys are always lowercase, this increases the
                    # chances that pre-existing languages will be recognized
                    language = attr[1].lower()
                    if (self.md_interpreter == 'misaka' or
                        self.md_interpreter is None):
                        self.handle_data("\n~~~ { %s }\n" % language)
                    elif self.md_interpreter == 'markdown':
                        self.handle_data("\n~~~\n:::%s\n" % language)
                    else:
                        raise Exception(
                            "Unknown markdown interpeter: %s" %
                            self.md_interpreter)
                    break
            else:
                self.handle_data("\n~~~\n")
        elif tag == 'code':
            self.handle_data('`')
        elif tag == 'p':
            self.handle_data('\n')
        elif tag == 'a':
            self.link = {'title': '', 'href': ''}
            for name, val in attrs:
                if name == 'href':
                    self.link['href'] = val
                elif name == 'title':
                    self.link['title'] = val
            self.handle_data('[')
        elif tag in ('em', 'i'):
            self.handle_data('_')
        elif tag in ('strong', 'b'):
            self.handle_data('**')
        else:
            # pass the data through
            atts = ' '.join('%s="%s"' % (a, v) for a, v in attrs)
            if atts:
                self.handle_data("<%s %s>" % (tag, atts))
            else:
                self.handle_data("<%s>" % tag)

    def handle_endtag(self, tag):
        if tag == 'pre':
            self.in_pre = False
            self.handle_data("\n~~~\n")
        elif tag == 'code':
            self.handle_data('`')
        elif tag == 'a':
            if self.link['title']:
                self.handle_data('](%(href)s "%(title)s") ' % self.link)
            else:
                self.handle_data('](%s) ' % self.link['href'])
        elif tag == 'p':
            self.handle_data('\n')
        elif tag in ('em', 'i'):
            self.append_endtag('_')
        elif tag in ('strong', 'b'):
            self.append_endtag('**')
        else:
            self.handle_data("</%s>" % tag)

class Exporter(object):
    """A class that wraps up export-logic.

    This class is meant to be used as a function: init it with the source
    file and the destination, and it will do the conversion.

    Why a class? Because that's how people write extensible code nowadays.
    Subclass this and write your own get_posts_from_* and export_to_* methods
    and you'll be golden.

    In more detail: to write an extractor, name it `get_props_from_FORMAT`
    where FORMAT is the name of the format to extract and make sure that it
    returns an iterable of dict-like objects that have at least the following
    keys:

        - u'date'
        - u'author'
        - u'content'
        - u'title'
        - u'status'
        - u'tags'
        - u'categories'
        - u'classifiers'

    And 'classifiers' is the union of 'tags' and 'categories'.

    To write an exporter, write something that takes that iterable of
    post-like things as well as a directory and creates files with those
    things. See the various export_to_* methods herein for examples.

    There are a couple utility methods that you can use to munge up some
    text, too.
    """

    def __init__(self, source, outdir,
                 source_format='wp_rss', dest_format='pelican'):
        # create an html-to-markdown processor md_interpreter is the target
        # md_interpreter. They have different ideas about what to send to
        # pygments
        md_interpreter = 'misaka' if dest_format == 'mynt' else 'markdown'
        self.processor = HtmlPreProcessor(md_interpreter)

        # actually do the stuff:
        posts = getattr(self, 'get_posts_from_%s' % source_format)(source)
        getattr(self, 'export_to_%s' % dest_format)(posts, outdir)

############################################################################
    # utility functions
    def _markdownify(self, content):
        """Convert some pseudo-html into reasonably pleasant text
        """
        self.processor.reset()
        self.processor.feed(content)
        return self.processor.readmd()

    @staticmethod
    def _slugify(txt):
        return txt.lower().strip()\
            .replace(',', '')\
            .replace('/', '+')\
            .replace(' ', '-')\
            .replace('.', '')

############################################################################
    # export functions
    def export_to_pelican(self, posts, base_dir):
        template = u"""Title: %(title)s
Slug: %(slug)s
Author: %(author)s
Status: %(status)s
Date: %(date)s
Tags: %(tags)s
Category: %(category)s

%(content)s
"""
        j = os.path.join
        for post in posts:
            if post['content'] is None:
                continue

            post['slug'] = self._slugify(post['title'])

            post['date'] = post['date'][:-3]
            post['content'] = self._markdownify(post['content'])

            # in pelican, each post can only be in ONE category, so put all
            # but the first into tags
            if len(post['categories']) > 0:
                post['category'] = post[u'categories'][0]
            else:
                post['category'] = ''
            post['tags'] = ', '.join(post[u'tags'] +
                                     post['categories'][1:])

            if post['status'] == 'publish':
                post['status'] = 'published'

            out = j(base_dir, post['slug'] + '.md')
            with open(out, 'w') as fh:
                print ('writing (%s) ' % post['status']) + out
                fh.write((template % post).encode('utf-8'))

    def export_to_nikola(self, posts, base_dir):
        meta_template = u"""%(title)s
%(safe_title)s
%(date)s
%(classifiers)s
"""
        j = os.path.join
        for post in posts:
            if post['content'] is None:
                continue

            t = post['safe_title'] = self._slugify(post['title'])

            post['date'] = post['date'].replace('-', '/')[:-3]
            post['content'] = self._markdownify(post['content'])
            post['classifiers'] = ', '.join(post['classifiers'])

            with open(j(base_dir, t + '.meta'), 'w') as metafh:
                metafh.write((meta_template % post).encode('utf-8'))

            with open(j(base_dir, t + '.md'), 'w') as postfh:
                postfh.write(post['content'].encode('utf-8'))

    def export_to_mynt(self, posts, base_dir):
        """Write blog stuff to mynt-like files

        Expects an iterable of dict-like objects that have the following fields:

            - `title` <string>
            - `tags`  <list>
            - `content` <string>

        All of these should be in a format ready to write.
        """

        template = u"""---
layout: post.html
title: %(title)s
tags: %(classifiers)s
---

%(content)s
"""
        opj = os.path.join

        for post in posts:
            if post['content'] is None:
                continue
            filename = post['date'] + '-' + post['title'] + '.md'
            filename = self._slugify(filename)

            # wordpress creates drafts with statuses draft or auto-draft
            # mynt ignores files that start with an underscore
            if 'draft' in post['status']:
                filename = '_' + filename

            # yaml has weird ideas about escape chars
            post['title'] = repr(post['title']).replace(
                r"\'", "''").replace("\\", "")

            post['content'] = self._markdownify(post['content'])

            with open(opj(base_dir, filename), 'w') as fh:
                out = template % post
                fh.write(out.encode('utf-8'))

############################################################################
    # import functions
    @staticmethod
    def get_posts_from_pma_xml(source):
        """Convert PHPMyAdmin xml to nice python Dicts

        this is where I implement database joins on top of xml.

        I try to be nice, and this is what I get? Sheesh. I hope somebody who
        doesn't have a mysql driver is grateful.
        """
        root = ET.parse(source).getroot()

        els = root.findall(".//table[@name='wp_posts']")
        posts = OrderedDict()

        terms = {}
        for term in root.findall(".//table[@name='wp_terms']"):
            key = term.find("./column[@name='term_id']").text
            tag = term.find("./column[@name='slug']").text
            terms[key] = tag

        taxes = {} # term taxonomy is the relationship between terms and parents
        categories  = {}
        for taxonomy in root.findall(".//table[@name='wp_term_taxonomy']"):
            tax = taxonomy.find("./column[@name='taxonomy']").text
            if tax == 'post_tag':
                key = taxonomy.find("./column[@name='term_taxonomy_id']").text
                term_id = taxonomy.find("./column[@name='term_id']").text
                taxes[key] = terms[term_id]

            elif tax == 'category':
                key = taxonomy.find("./column[@name='term_taxonomy_id']").text
                term_id = taxonomy.find("./column[@name='term_id']").text
                categories[key] = terms[term_id]

        users = {}
        for user_el in root.findall(".//table[@name='wp_users']"):
            id  = user_el.find("./column[@name='ID']").text
            name = user_el.find("./column[@name='display_name']").text
            users[id] = name

        all_tags = {}
        all_tags.update(taxes)
        all_tags.update(categories)
        post_classifiers = defaultdict(list)
        post_cats = defaultdict(list)
        post_tags = defaultdict(list)
        for relation in root.findall(".//table[@name='wp_term_relationships']"):
            obj_id  = relation.find("./column[@name='object_id']").text
            term_id = relation.find("./column[@name='term_taxonomy_id']").text
            try:
                term = all_tags[term_id] # should throw KeyError for links
                post_classifiers[obj_id].append(term)
            except KeyError:
                pass

            try:
                # throw keyerror if this post doesn't have a category
                cat = categories[term_id]
                post_cats[obj_id].append(cat)
            except KeyError:
                pass

            try:
                # throw keyerror if this post doesn't have this tag
                tag = taxes[term_id]
                post_tags[obj_id].append(tag)
            except KeyError:
                pass

        for el in els:
            id = el.find("./column[@name='ID']").text
            author_id = el.find("./column[@name='post_author']").text
            author = users[author_id]
            post_type = el.find("./column[@name='post_type']").text
            status = el.find("./column[@name='post_status']").text
            if post_type == 'revision':
                id = el.find("./column[@name='post_parent']").text
                if status == u'inherit':
                    status = posts[id][u'status']

            posts[id] = {
                u'date':    el.find("./column[@name='post_date']").text,
                u'author':  author,
                u'content': el.find("./column[@name='post_content']").text,
                u'title':   el.find("./column[@name='post_title']").text,
                u'status':  status,
                u'classifiers':    post_classifiers[id],
                u'categories': post_cats[id],
                u'tags': post_tags[id],
                }

        return posts.itervalues()

    @staticmethod
    def get_posts_from_wp_rss(filename):
        rss = ET.parse(filename).getroot()

        # namespaced elements are expanded according to xml rules to look
        # like '{long/namespace}element', and for some reasona I can't create
        # a name mapping inside of etree to allow me to access e.g.
        # wp:element elements. Hence these namespace functions.
        def wp(element):
            return u'{http://wordpress.org/export/1.1/}%s' % element
        def dc(element):
            return u'{http://purl.org/dc/elements/1.1/}%s' % element
        def content(el):
            return u'{http://purl.org/rss/1.0/modules/content/}%s' % el

        for post_el in rss.findall('channel/item'):
            post = {}
            post['date']  = post_el.find(wp('post_date')).text
            post['author'] = post_el.find(dc('creator')).text
            post['content'] = post_el.find(content('encoded')).text
            post['title'] = post_el.find('title').text
            post['status'] = post_el.find(wp('status')).text
            post['categories'] = []
            post['tags'] = []
            post['classifiers'] = []
            for classifier in post_el.findall('category'):
                cl = classifier.text
                post['classifiers'].append(cl)
                if classifier.get('domain') == 'category':
                    post['categories'].append(cl)
                else:
                    # tags are the most general sort of classifier we've got
                    # access to
                    post['tags'].append(cl)

            yield post

def parse_args(args):
    parser = argparse.ArgumentParser(
        description="Convert WordPress data from on giant xml file into a "
        "bunch of Markdown files.",
        epilog="""The defaults have been chosen to be commonly useful if you
        just want a readable version of your blog. Run ``%(prog)s source.xml
        destination`` and you'll end up with a bunch of files named after
        your blog titles. Home Page: http://github.com/quodlibetor/wp-md""")

    parser.add_argument('source', metavar="<blog.xml>",
                        help="The file to convert")
    parser.add_argument('dest', metavar="<output_folder>",
                        help="The folder to put the converted files in")
    parser.add_argument('--of', "--output-format",
                        choices=("pelican", "nikola", "mynt"),
                        default="pelican",
                        dest="output_format",
                        help="The output format. These match the data formats"
                        " expected by the named static site generators.")
    parser.add_argument('--if', "--input-format",
                        choices=("pma_xml", "wp_rss"),
                        default='wp_rss',
                        dest="input_format",
                        help="The input format: either PHPMyAdmin xml "
                        "or WordPress eXtended RSS (v1.1). If you are "
                        "unsure which one you have it's probably wp_rss."
                        )
    parser.add_argument('--version',
                        action='version',
                        version='%(prog)s ' + VERSION)


    return parser.parse_args(args[1:])

def main():
    args = parse_args(sys.argv)

    if not os.path.isdir(args.dest):
        if os.path.exists(args.dest):
            exit("Destination should be a directory, not a file.")

        os.makedirs(args.dest)

    Exporter(args.source, args.dest,
             args.input_format, args.output_format)

if __name__ == '__main__':
    main()
