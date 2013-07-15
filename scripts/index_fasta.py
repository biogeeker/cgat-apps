################################################################################
#
#   MRC FGU Computational Genomics Group
#
#   $Id$
#
#   Copyright (C) 2009 Andreas Heger
#
#   This program is free software; you can redistribute it and/or
#   modify it under the terms of the GNU General Public License
#   as published by the Free Software Foundation; either version 2
#   of the License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software
#   Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#################################################################################
'''
index_fasta.py - Index fasta formatted files 
============================================

:Author: Andreas Heger
:Release: $Id$
:Date: |today|
:Tags: Python

Purpose
-------

This script indexes one or more :term:`fasta` formatted files into a 
database that can be used by :mod:`IndexedFasta` for quick acces to
sequences.

By default, the database itself is a :term:`fasta` formatted file
itself. Compression methods are available to conserve disk space,
though they do come at a performance penalty.

See also http://pypi.python.org/pypi/pyfasta for a similar
implementation.

For example, to index a collection of fasta files::

  python index_fasta.py oa_ornAna1_softmasked ornAna1.fa.gz > oa_ornAna1_softmasked.log

To retrieve a segment::

  python index_fasta.py --extract=chr5:1000:2000 oa_ornAna1_softmasked 

Usage
-----

Example::

   python index_fasta.py oa_ornAna1_softmasked /net/cpp-mirror/ucsc/ornAna1/bigZips/ornAna1.fa.gz > oa_ornAna1_softmasked.log

Type::

   python index_fasta.py --help

for command line help.

Documentation
-------------

Code
----

'''
import CGAT.IndexedFasta as IndexedFasta
import CGAT.Experiment as E
import sys, re, os

def main():


    parser = E.OptionParser( version = "%prog version: $Id: IndexedFasta.py 2801 2009-10-22 13:40:39Z andreas $", 
                             usage = globals()["__doc__"])

    parser.add_option( "-e", "--extract", dest="extract", type="string",
                       help="extract region for testing purposes. Format is contig:strand:from:to. "
                            "The default coordinates are 0-based open/closed coordinates on both strands. "
                            "For example, chr1:+:10:12 will return bases 11 to 12 on chr1." )

    parser.add_option( "-c", "--compression", dest="compression", type="choice",
                       choices=("lzo", "zlib", "gzip", "dictzip", "bzip2", "debug"),
                       help="compress database [default=%default]." )

    parser.add_option( "--random-access-points", dest="random_access_points", type="int",
                       help="save random access points every # number of nucleotides [default=%default]." )

    parser.add_option( "-i", "--input-format", dest="input_format", type="choice",
                       choices=("one-forward-open", "zero-both-open" ),
                       help="coordinate format of input [default=%default]." )

    parser.add_option( "-s", "--synonyms", dest="synonyms", type="string",
                       help="list of synonyms, comma separated with =, for example, chr1=chr1b [default=%default]" )

    parser.add_option( "-b", "--benchmark", dest="benchmark", action="store_true",
                       help="benchmark time for read access [default=%default]." )
    
    parser.add_option( "--benchmark-num-iterations", dest="benchmark_num_iterations", type="int",
                       help="number of iterations for benchmark [default=%default]." )

    parser.add_option( "--benchmark-fragment-size", dest="benchmark_fragment_size", type="int",
                       help="benchmark: fragment size [default=%default]." )

    parser.add_option( "--verify", dest="verify", type="string",
                       help="verify against other database [default=%default].")

    parser.add_option( "-a", "--clean-sequence", dest="clean_sequence", action="store_true",
                       help="remove X/x from DNA sequences - they cause errors in exonerate [default=%default]." )

    parser.add_option( "--allow-duplicates", dest="allow_duplicates", action="store_true",
                       help="allow duplicate identifiers. Further occurances of an identifier are suffixed by an '_%i' [default=%default]." )

    parser.add_option( "--regex-identifier", dest="regex_identifier", type="string",
                       help="regular expression for extracting the identifier from fasta description line [default=%default]." )

    parser.add_option( "--compress-index", dest="compress_index", action="store_true",
                       help="compress index [default=%default]." )

    parser.add_option( "--force", dest="force", action="store_true",
                       help="force overwriting of existing files [default=%default]." )

    parser.add_option( "-t", "--translator", dest="translator", type="choice",
                       choices=("solexa", "phred", "bytes", "range200" ),
                       help="translate numerical quality scores [default=%default]." )


    parser.set_defaults(
        extract = None,
        input_format = "zero-both-open",
        benchmark_fragment_size = 1000,
        benchmark_num_iterations = 1000000,
        benchmark = False,
        compression = None,
        random_access_points = 0,
        synonyms = None,
        verify = None,
        verify_num_iterations = 100000,
        verify_fragment_size = 100,
        clean_sequence = False,
        allow_duplicates = False,
        regex_identifier = None,
        compress_index = False,
        force = False,
        translator = None )
    
    (options, args) = E.Start( parser )

    if options.synonyms:
        synonyms = {}
        for x in options.synonyms.split(","):
            a,b = x.split("=")
            a = a.strip()
            b = b.strip()
            if a not in synonyms: synonyms[a] = []
            synonyms[a].append( b )
    else:
        synonyms = None

    if options.translator:
        if options.translator == "phred":
            options.translator = TranslatorPhred()
        elif options.translator == "solexa":
            options.translator = TranslatorSolexa()
        elif options.translator == "bytes":
            options.translator = TranslatorBytes()
        elif options.translator == "range200":
            options.translator = TranslatorRange200()
        else:
            raise ValueError("unknown translator %s" % options.translator)
        
    if options.extract:
        fasta = IndexedFasta.IndexedFasta( args[0] )
        fasta.setTranslator( options.translator )
        converter = IndexedFasta.getConverter( options.input_format )
        
        contig, strand, start, end = IndexedFasta.parseCoordinates( options.extract )
        sequence = fasta.getSequence( contig, strand,
                                      start, end,
                                      converter = converter )
        options.stdout.write( ">%s\n%s\n" % \
                              ( options.extract, sequence ) )
    elif options.benchmark:
        import timeit
        timer = timeit.Timer( stmt="benchmarkRandomFragment( fasta = fasta, size = %i)" % (options.benchmark_fragment_size),
                              setup="""from __main__ import benchmarkRandomFragment,IndexedFasta\nfasta=IndexedFasta.IndexedFasta( "%s" )""" % (args[0] ) )

        t = timer.timeit( number = options.benchmark_num_iterations )
        options.stdout.write("iter\tsize\ttime\n" )
        options.stdout.write("%i\t%i\t%i\n" % (options.benchmark_num_iterations, options.benchmark_fragment_size, t ) )
    elif options.verify:
        fasta1 = IndexedFasta.IndexedFasta( args[0] ) 
        fasta2 = IndexedFasta.IndexedFasta( options.verify )
        nerrors1 = verify( fasta1, fasta2,
                           options.verify_num_iterations,
                           options.verify_fragment_size,
                           stdout=options.stdout )
        options.stdout.write("errors=%i\n" % (nerrors1) )        
        nerrors2 = IndexedFasta.verify( fasta2, fasta1,
                                        options.verify_num_iterations,
                                        options.verify_fragment_size,
                                        stdout=options.stdout )
        options.stdout.write("errors=%i\n" % (nerrors2) )        
    elif options.compress_index:
        fasta = IndexedFasta.IndexedFasta( args[0] ) 
        fasta.compressIndex()
    else:
        if options.loglevel >= 1:
            options.stdlog.write("# creating database %s\n" % args[0])            
            options.stdlog.write("# indexing the following files: \n# %s\n" %\
                                 (" \n# ".join( args[1:] ) ))
            options.stdlog.flush()

            if synonyms:
                options.stdlog.write("# Applying the following synonyms:\n" )
                for k,v in synonyms.items():
                    options.stdlog.write( "# %s=%s\n" % (k, ",".join(v) ) )
                options.stdlog.flush()
        if len(args) < 2:
            print globals()["__doc__"]
            sys.exit(1)
            
        iterator = IndexedFasta.MultipleFastaIterator( args[1:],     
                                                       regex_identifier = options.regex_identifier )

        IndexedFast.createDatabase( args[0], 
                                    iterator, 
                                    synonyms = synonyms,
                                    random_access_points = options.random_access_points,
                                    compression = options.compression,
                                    clean_sequence = options.clean_sequence,
                                    allow_duplicates = options.allow_duplicates,
                                    translator = options.translator,
                                    force = options.force )

    
    E.Stop()

if __name__ == "__main__": 
    sys.exit( main() )

