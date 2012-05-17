========
 WP, MD
========

Dammit, Jim! I'm a hack, not a program!
=======================================

:author: Brandon W Maister <quodlibetor@gmail.com>
:Homepage: http://github.com/quolibetor/wp-md
:copyright: MIT: take, use, share

What it is
----------

This script converts blog posts from WordPress's xml formats to one of
various markdown-using static-site generator formats.

What that means is that you get a more human-readable version of your WordPress blogs if you run the wordpress export file through wp-md.

Why?
~~~~

I want to leave WordPress, primarily because it's friggin' impossible to provide code samples within it.

But I want syntax-highlighted code, so I need to export all my existing posts to something reasonable and none of the existing HTML->markdown converters seem to do a good job with both WordPress' pseudo-html *and* getting the code blocks to be syntax-aware.

This does.

It's also pretty bad at it's job, so it's fairly fast. (Much faster than pandoc, anyway.)

The main thing that this does *not* do is any conversion of nested elements: ``<ol>``, ``<blockquote>`` and their ilk are just passed through to the final file. This works fine because HTML is valid Markdown.

wpmd also works with WordPress' eXtended RSS or PHPMyAdmin database xml format, so it doesn't need a database layer, or a database.

Installation
------------

To put the script on your path do::

    python setup.py install

or::

    pip install wp-md

Otherwise, just substitue ``wpmd.py`` for ``wp-md`` as the name of the program in this document, it'll work.

Usage
-----

Go to WordPress' export page in the admin and download ``your-blog.xml``, then::

    wp-md your-blog.xml blog-files

will put a whole bunch of files in the directory ``blog-files``, creating it if it doesn't exist.

You can run wp-md with the ``--output-format`` flag to choose which static-site generator format you want your posts to be exported as:

    - Nikola_
    - Mynt_
    - Pelican_

The current default is Pelican_ because it puts the most metadata into the file, and doesn't require the date to be in the filename. If you *want* the date to be part of the filename, use the Mynt_ format.

If you happen to have a PHPMyAdmin export of your database, you can use the ``--input-format`` flag to choose ``pma_xml``.

.. _Nikola: http://nikola.ralsina.com.ar/
.. _Mynt: http://mynt.mirroredwhite.com/
.. _Pelican: http://pelican.notmyidea.org/en/latest/

Notes
-----

This is a semi-useful hack that I wrote so that I could play around with static site generators. I don't know that it will work for you, but if it's missing a feature that you want let me know and I might oblige.

Developers
----------

The code is reasonably well documented and tiny, pull requests welcome.

License
-------

Share and use, and give me credit if you feel like it.

MIT::

    The MIT License (MIT)

    Copyright (c) 2012 Brandon W Maister <quodlibetor@gmail.com>

    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the
    "Software"), to deal in the Software without restriction, including
    without limitation the rights to use, copy, modify, merge, publish,
    distribute, sublicense, and/or sell copies of the Software, and to permit
    persons to whom the Software is furnished to do so, subject to the
    following conditions:

    The above copyright notice and this permission notice shall be included
    in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
    OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
    MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
    NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
    DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
    OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
    USE OR OTHER DEALINGS IN THE SOFTWARE.
