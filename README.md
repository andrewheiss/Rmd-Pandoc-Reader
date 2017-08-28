# Rmd Pandoc Reader

This plugin is essentially the combination of the [RMD Reader](https://github.com/getpelican/pelican-plugins/tree/master/rmd_reader) and the [Pandoc Reader](https://github.com/liob/pandoc_reader) plugins for [Pelican](http://docs.getpelican.com/en/stable/). 

It solves one crucial issue with the RMD Reader plugin: **you cannot use pandoc-flavored Markdown in `Rmd` files if you use the regular RMD Reader plugin.** When you use RStudio to knit an `Rmd` file, it uses pandoc as the Markdown parser, but when you use the RMD Reader plugin with Pelican, it uses [Python's Markdown library](https://pythonhosted.org/Markdown/) as the Markdown parser. 

While there's no difference between standard Markdown syntax like `*italics*` and `## Headings`, Python's Markdown cannot handle fancier things like [multi-line tables](http://pandoc.org/MANUAL.html#extension-multiline_tables) or [citations](http://pandoc.org/MANUAL.html#citations). Complicating matters further, if you use pandoc-flavored Markdown on normal `md` files, enabling the RMD Reader plugin forces you to use Python's Markdown instead of pandoc, thus breaking everything.

This plugin gives you the best of both worlds—you can parse and knit `Rmd` files *and* parse regular `md` files with pandoc.

## Usage

Since I essentially merged the pandoc processing section of Pandoc Reader into RMD Reader, the usage and configuration options are the same as their standalone plugins, so consult each plugin. Make sure pandoc is in your `$PATH`, following [the instructions from Pandoc Reader](https://github.com/liob/pandoc_reader#configuration), and that you include whatever Rmd knitting options you want in `pelicanconf.py`, following [the instructions from RMD Reader](https://github.com/getpelican/pelican-plugins/tree/master/rmd_reader#usage).

Make sure you have both `pandoc_reader` and `rmd_pandoc_reader` enabled in `pelicanconf.py`, with `rmd_pandoc_reader` last:

    PLUGINS = ['pandoc_reader', 'rmd_pandoc_reader']

The Pandoc Reader plugin will handle all your regular Markdown files while this plugin will handle your `Rmd` files *using pandoc*.
