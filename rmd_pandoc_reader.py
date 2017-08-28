import os
import warnings
import logging
import subprocess

from pelican import readers
from pelican import signals
from pelican import settings
from pelican.utils import pelican_open, SafeDatetime, get_date

import datetime
import pytz
import frontmatter

logger = logging.getLogger('RMD_READER')

KNITR = None
RMD = False
FIG_PATH = None
R_STARTED = False

def startr():
    global KNITR, R_OBJECTS, R_STARTED
    if R_STARTED:
        return
    logger.debug('STARTING R')
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import rpy2.rinterface
        rpy2.rinterface.set_initoptions((b'rpy2', b'--no-save', b'--vanilla', b'--quiet'))
        import rpy2.robjects as R_OBJECTS
        from rpy2.robjects.packages import importr
    KNITR = importr('knitr')
    logger.debug('R STARTED')
    R_STARTED = True

def initsignal(pelicanobj):
    global RMD, FIG_PATH
    try:
        startr()
        R_OBJECTS.r('Sys.setlocale("LC_ALL", "C")')
        R_OBJECTS.r('Sys.setlocale("LC_NUMERIC", "C")')
        R_OBJECTS.r('Sys.setlocale("LC_MESSAGES", "C")')

        idx = KNITR.opts_knit.names.index('set')
        path = pelicanobj.settings.get('PATH', '%s/content' % settings.DEFAULT_CONFIG.get('PATH'))
        logger.debug("RMD_READER PATH = %s", path)
        KNITR.opts_knit[idx](**{'base.dir': path})

        knitroptsknit = pelicanobj.settings.get('RMD_READER_KNITR_OPTS_KNIT', None)
        if knitroptsknit:
            KNITR.opts_knit[idx](**{str(k): v for k, v in knitroptsknit.items()})

        idx = KNITR.opts_chunk.names.index('set')
        knitroptschunk = pelicanobj.settings.get('RMD_READER_KNITR_OPTS_CHUNK', None)
        if knitroptschunk:
            FIG_PATH = knitroptschunk['fig.path'] if 'fig.path' in knitroptschunk else 'figure/'
            KNITR.opts_chunk[idx](**{str(k): v for k, v in knitroptschunk.items()})

        RMD = True
    except ImportError as ex:
        RMD = False

class RmdPandocReader(readers.BaseReader):
    file_extensions = ['Rmd', 'rmd']

    @property
    def enabled():
        return RMD

    # You need to have a read method, which takes a filename and returns
    # some content and the associated metadata.
    def read(self, filename):
        """Parse content and metadata of markdown files"""
        QUIET = self.settings.get('RMD_READER_KNITR_QUIET', True)
        ENCODING = self.settings.get('RMD_READER_KNITR_ENCODING', 'UTF-8')
        CLEANUP = self.settings.get('RMD_READER_CLEANUP', True)
        RENAME_PLOT = self.settings.get('RMD_READER_RENAME_PLOT', 'chunklabel')
        if type(RENAME_PLOT) is bool:
            logger.error("RMD_READER_RENAME_PLOT takes a string value (either chunklabel or directory), please see the readme.")
            if RENAME_PLOT:
                RENAME_PLOT = 'chunklabel'
                logger.error("Defaulting to chunklabel")
            else:
                RENAME_PLOT = 'disabled'
                logger.error("Disabling plot renaming")
        logger.debug("RMD_READER_KNITR_QUIET = %s", QUIET)
        logger.debug("RMD_READER_KNITR_ENCODING = %s", ENCODING)
        logger.debug("RMD_READER_CLEANUP = %s", CLEANUP)
        logger.debug("RMD_READER_RENAME_PLOT = %s", RENAME_PLOT)
        # replace single backslashes with double backslashes
        filename = filename.replace('\\', '\\\\')

        # parse Rmd file - generate md file
        md_filename = filename.replace('.Rmd', '.aux').replace('.rmd', '.aux')
        if RENAME_PLOT == 'chunklabel' or RENAME_PLOT == 'directory':
            if RENAME_PLOT == 'chunklabel':
                chunk_label = os.path.splitext(os.path.basename(filename))[0]
                logger.debug('Chunk label: %s', chunk_label)
            elif RENAME_PLOT == 'directory':
                chunk_label = 'unnamed-chunk'
                PATH = self.settings.get('PATH', '%s/content' % settings.DEFAULT_CONFIG.get('PATH'))
                src_name = os.path.splitext(os.path.relpath(filename, PATH))[0]
                idx = KNITR.opts_chunk.names.index('set')
                knitroptschunk = {'fig.path': '%s-' % os.path.join(FIG_PATH, src_name)}
                KNITR.opts_chunk[idx](**{str(k): v for k, v in knitroptschunk.items()})
                logger.debug('Figures path: %s, chunk label: %s', knitroptschunk['fig.path'], chunk_label)
            R_OBJECTS.r('''
opts_knit$set(unnamed.chunk.label="{unnamed_chunk_label}")
render_markdown()
hook_plot <- knit_hooks$get('plot')
knit_hooks$set(plot=function(x, options) hook_plot(paste0("{{filename}}/", x), options))
            '''.format(unnamed_chunk_label=chunk_label))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            KNITR.knit(filename, md_filename, quiet=QUIET, encoding=ENCODING)

        # Open the file and separate the metadata from the content with frontmatter
        with pelican_open(md_filename) as fp:
            metadata_raw, content = frontmatter.parse(fp)

        # Convert the metadata to Pelican's format
        metadata = {}
        for name, value in metadata_raw.items():
            name = name.lower()
            # frontmatter converts dates to datetime.date or datetime.datetime objects, but Pelican chokes on plain datetime.date objects, so if it's just a date, make it a time too and add the timezone
            if isinstance(value, datetime.date):
                # Combine date with datetime.time(0, 0)
                date_time = datetime.datetime.combine(value, datetime.datetime.min.time())

                # Add timezone
                tz = pytz.timezone(self.settings.get('TIMEZONE', None))
                date_time_tz = tz.localize(date_time)

                metadata[name] = date_time_tz
            else:
                meta = self.process_metadata(name, value)
                metadata[name] = meta

        # Pandoc settings
        extra_args = self.settings.get('PANDOC_ARGS', [])
        extensions = self.settings.get('PANDOC_EXTENSIONS', '')
        if isinstance(extensions, list):
            extensions = ''.join(extensions)

        pandoc_cmd = ["pandoc", "--from=markdown" + extensions, "--to=html5"]
        pandoc_cmd.extend(extra_args)

        proc = subprocess.Popen(pandoc_cmd,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE)

        content = content.replace('{filename}', '')

        # Convert content to HTML with pandoc
        output = proc.communicate(content.encode('utf-8'))[0].decode('utf-8')
        status = proc.wait()
        if status:
            raise subprocess.CalledProcessError(status, pandoc_cmd)

        # Remove temporary file
        if CLEANUP:
            os.remove(md_filename)

        # All done!
        return output, metadata

def add_reader(readers):
    readers.reader_classes['rmd'] = RmdPandocReader

def register():
    signals.readers_init.connect(add_reader)
    signals.initialized.connect(initsignal)
