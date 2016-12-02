import os
import sys
import argparse
import textwrap as _textwrap

from .module import CLIModule

class _MultilineHelpFormatter(argparse.HelpFormatter):
    def _fill_text(self, text, width, indent):
        text = self._whitespace_matcher.sub(' ', text).strip()
        paragraphs = text.split('|n')
        multiline_text = ''
        for paragraph in paragraphs:
            formatted_paragraph = '\n' + _textwrap.fill(
                paragraph, width,
                initial_indent=indent,
                subsequent_indent=indent) + '\n'
            multiline_text += formatted_paragraph
        return multiline_text


def _make_print_xml_action(xml_spec_file):

    # read xml spec file into a string
    with open(xml_spec_file) as f:
        str_xml = f.read()

    class _PrintXMLAction(argparse.Action):

        def __init__(self,
                     option_strings,
                     dest=argparse.SUPPRESS,
                     default=argparse.SUPPRESS,
                     help=None):
            super(_PrintXMLAction, self).__init__(
                option_strings=option_strings,
                dest=dest,
                default=default,
                nargs=0,
                help=help)

        def __call__(self, parser, namespace, values, option_string=None):
            print(str_xml)
            parser.exit()

    return _PrintXMLAction


class CLIArgumentParser(argparse.ArgumentParser):
    def __init__(self, xml_spec_file=None):

        # call and initialize super class
        super(CLIArgumentParser, self).__init__(
            formatter_class=_MultilineHelpFormatter
        )

        # get xml spec file
        if xml_spec_file is None:
            xml_spec_file = os.path.splitext(sys.argv[0])[0] + '.xml'

        # parse xml spec file
        clim = CLIModule(xml_spec_file)

        # add description as epilog
        str_description = ['Title: ' + clim.title,
                           'Description: ' + clim.description]

        if clim.contributor is not None and len(clim.contributor) > 0:
            str_description.append('Author(s): ' + clim.contributor)

        if clim.license is not None and len(clim.license) > 0:
            str_description.append('License: ' + clim.license)

        if clim.acknowledgements is not None and \
           len(clim.acknowledgements) > 0:
            str_description.append(
                'Acknowledgements: ' + clim.acknowledgements)

        self.epilog = '|n'.join(str_description)

        # add version
        if clim.version is not None:
            self.add_argument(
                '-V', '--version',
                action='version',
                version=clim.version
            )

        # add --xml action
        self.add_argument(
            '--xml',
            action=_make_print_xml_action(xml_spec_file),
            help='Produce xml description of command line arguments')

        # get parameters
        index_params, opt_params, simple_out_params = clim.classifyParameters()

        for p in simple_out_params:
            if p.index is not None:
                index_params.append(p)
            elif p.flag or p.longflag:
                opt_params.append(p)

        # sort indexed parameters in increasing order of index
        index_params.sort(key=lambda p: p.index)

        # sort opt parameters in increasing order of name for easy lookup
        def get_flag(p):
            if p.flag is not None:
                return p.flag.strip('-')
            elif p.longflag is not None:
                return p.longflag.strip('-')
            else:
                return None

        opt_params.sort(key=lambda p: get_flag(p))

        # if xml spec has simple output parameters add returnparameterfile
        if len(simple_out_params) > 0:
            self.add_argument(
                '--returnparameterfile',
                dest='returnParameterFile',
                metavar='<file>',
                type=str,
                help=' Filename in which to write simple return parameters '
                '(integer, float, integer-vector, etc.) as opposed to bulk '
                'return parameters (image, file, directory, geometry, '
                'transform, measurement, table).'
            )

        # add index parameters as positional arguments
        for param in index_params:

            cur_kwargs = {
                'type': param.parseValue,
                'help': param.description + ' (type: %s)' % param.typ,
            }

            if param.elements is not None:
                cur_kwargs['choices'] = param.elements

            if param.multiple:
                cur_kwargs['nargs'] = '+'
                cur_kwargs['action'] = 'append'

            if param.fileExtensions is not None:
                cur_kwargs['help'] +=\
                    ' (file-extensions: %s)' % param.fileExtensions

            self.add_argument(param.name, **cur_kwargs)

        # add optional parameters as optional arguments
        for param in opt_params:

            cur_args = []
            if param.flag is not None:
                cur_args.append(param.flag)
            if param.longflag is not None:
                cur_args.append(param.longflag)
            if len(cur_args) == 0:
                continue

            cur_kwargs = {
                'dest': param.name,
                'type': param.parseValue,
                'help': param.description,
            }

            if param.elements is not None:
                cur_kwargs['choices'] = param.elements
            else:
                cur_kwargs['metavar'] = '<%s>' % param.typ

            if param.multiple:
                cur_kwargs['action'] = 'append'
                cur_kwargs['help'] += ' (accepted multiple times)'

            if param.default is not None:
                cur_kwargs['default'] = param.default
                cur_kwargs['help'] += ' (default: %s)' % param.default

            if param.fileExtensions is not None:
                cur_kwargs['help'] +=\
                    ' (file-extensions: %s)' % param.fileExtensions

            self.add_argument(*cur_args, **cur_kwargs)

