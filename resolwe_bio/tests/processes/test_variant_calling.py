# pylint: disable=missing-docstring
from os.path import join

from resolwe.test import tag_process
from resolwe_bio.utils.filter import filter_vcf_variable
from resolwe_bio.utils.test import skipDockerFailure, skipUnlessLargeFiles, BioProcessTestCase


class VariantCallingTestCase(BioProcessTestCase):

    @tag_process('vc-samtools')
    def test_variant_calling_samtools(self):
        with self.preparation_stage():
            inputs = {"src": "variant_calling_genome.fasta.gz"}
            genome = self.run_process('upload-genome', inputs)

            reads = self.prepare_reads(['variant_calling_reads.fastq.gz'])

            inputs = {'genome': genome.pk, 'reads': reads.pk, 'reporting': {'rep_mode': "def"}}
            aligned_reads = self.run_process('alignment-bowtie2', inputs)

        inputs = {
            'genome': genome.pk,
            'mapping': aligned_reads.pk,
            'options': {
                'd': 10,
                'D': 50000,
                'Q': 30
            }
        }
        samtools_variants = self.run_process('vc-samtools', inputs)
        self.assertFile(samtools_variants, 'vcf', 'variant_calling_samtools.vcf', file_filter=filter_vcf_variable)

    @tag_process('vc-chemut')
    def test_variant_calling_chemut(self):
        with self.preparation_stage():
            inputs = {'src': 'chemut_genome.fasta.gz'}
            genome = self.run_process('upload-genome', inputs)

            inputs = {'src1': ['AX4_mate1.fq.gz'],
                      'src2': ['AX4_mate2.fq.gz']}

            parental_reads = self.run_process('upload-fastq-paired', inputs)

            inputs = {'src1': ['CM_mate1.fq.gz'],
                      'src2': ['CM_mate2.fq.gz']}

            mut_reads = self.run_process('upload-fastq-paired', inputs)

            inputs = {'genome': genome.id, 'reads': parental_reads.id}
            align_parental = self.run_process('alignment-bwa-mem', inputs)

            inputs = {'genome': genome.id, 'reads': mut_reads.id}
            align_mut = self.run_process('alignment-bwa-mem', inputs)

        inputs = {
            'genome': genome.pk,
            'parental_strains': [align_parental.id],
            'mutant_strains': [align_mut.id],
            'reads_info': {
                'PL': "Illumina",
                'LB': "x",
                'CN': "def",
                'DT': "2014-08-05"},
            'Varc_param': {'stand_emit_conf': 10, 'stand_call_conf': 30}}

        self.run_process('vc-chemut', inputs)

    @tag_process('filtering-chemut')
    def test_filtering_chemut(self):
        with self.preparation_stage():
            variants = self.run_process('upload-variants-vcf', {'src': 'variant_calling_filtering.vcf.gz'})

        inputs = {
            'variants': variants.pk,
            'analysis_type': 'snv',
            'parental_strain': 'AX4',
            'mutant_strain': 'mutant',
            'read_depth': 5}

        filtered_variants = self.run_process('filtering-chemut', inputs)
        self.assertFile(filtered_variants, 'vcf', 'variant_calling_filtered_variants.vcf')

    @tag_process('hsqutils-dedup')
    def test_hsqutils_dedup(self):
        with self.preparation_stage():
            bam = self.run_process('upload-bam', {'src': 'hsqutils_aligment.bam'})

            inputs = {
                'src1': ['hsqutils_reads_mate1_paired_filtered.fastq.gz'],
                'src2': ['hsqutils_reads_mate2_paired_filtered.fastq.gz']}
            reads = self.run_processor('upload-fastq-paired', inputs)

            probe = self.run_processor('upload-file', {'src': 'hsqutils_probe_info.txt'})

        inputs = {
            'alignment': bam.id,
            'reads': reads.id,
            'probe': probe.id
        }

        hsqutils_dedup = self.run_process('hsqutils-dedup', inputs)
        self.assertFile(hsqutils_dedup, 'summary', 'HSQUtils_dedup_summary.txt')

    @skipDockerFailure("Processor requires a custom Docker image.")
    @skipUnlessLargeFiles('56GSID_10k_mate1_RG.bam')
    @tag_process('vc-realign-recalibrate')
    def test_vc_preprocess_bam(self):
        with self.preparation_stage():
            bam = self.run_process('upload-bam', {'src': join('large', '56GSID_10k_mate1_RG.bam')})
            genome = self.run_process('upload-genome', {'src': 'hs_b37_chr2_small.fasta.gz'})

            inputs = {'src': '1000G_phase1.indels.b37_chr2_small.vcf.gz'}
            indels = self.run_process('upload-variants-vcf', inputs)

            dbsnp = self.run_process('upload-variants-vcf', {'src': 'dbsnp_138.b37.chr2_small.vcf.gz'})

        inputs = {
            'alignment': bam.id,
            'genome': genome.id,
            'known_indels': [indels.id],
            'known_vars': [dbsnp.id]
        }

        self.run_process('vc-realign-recalibrate', inputs)

    @skipDockerFailure("Processor requires a custom Docker image.")
    @skipUnlessLargeFiles('56GSID_10k_mate1_RG.bam')
    @tag_process('picard-pcrmetrics')
    def test_collecttargetedpcrmetrics(self):
        with self.preparation_stage():
            bam = self.run_process('upload-bam', {'src': join('large', '56GSID_10k_mate1_RG.bam')})
            master_file = self.prepare_amplicon_master_file()
            genome = self.run_process('upload-genome', {'src': 'hs_b37_chr2_small.fasta.gz'})

        inputs = {
            'alignment': bam.id,
            'master_file': master_file.id,
            'genome': genome.id
        }

        self.run_process('picard-pcrmetrics', inputs)

    @skipDockerFailure("Processor requires a custom Docker image.")
    @skipUnlessLargeFiles('56GSID_10k.realigned.bqsrCal.bam')
    @tag_process('vc-gatk-hc')
    def test_gatk_haplotypecaller(self):
        with self.preparation_stage():
            alignment = self.run_process(
                'upload-bam',
                {'src': join('large', '56GSID_10k.realigned.bqsrCal.bam')}
            )
            genome = self.run_process('upload-genome', {'src': 'hs_b37_chr2_small.fasta.gz'})
            master_file = self.prepare_amplicon_master_file()
            dbsnp = self.run_process('upload-variants-vcf', {'src': 'dbsnp_138.b37.chr2_small.vcf.gz'})

        inputs = {
            'alignment': alignment.id,
            'intervals': master_file.id,
            'genome': genome.id,
            'dbsnp': dbsnp.id
        }

        gatk_vars = self.run_process('vc-gatk-hc', inputs)
        self.assertFile(gatk_vars, 'vcf', '56GSID_10k.gatkHC.vcf', file_filter=filter_vcf_variable)

    @skipUnlessLargeFiles('56GSID_10k.realigned.bqsrCal.bam')
    @tag_process('lofreq')
    def test_lofreq(self):
        with self.preparation_stage():
            alignment = self.run_process(
                'upload-bam',
                {'src': join('large', '56GSID_10k.realigned.bqsrCal.bam')}
            )
            genome = self.run_process('upload-genome', {'src': 'hs_b37_chr2_small.fasta.gz'})
            master_file = self.prepare_amplicon_master_file()

        inputs = {
            'alignment': alignment.id,
            'intervals': master_file.id,
            'genome': genome.id,
        }

        lofreq_vars = self.run_process('lofreq', inputs)
        self.assertFile(lofreq_vars, 'vcf', '56GSID_10k.lf.vcf', file_filter=filter_vcf_variable)

    @tag_process('snpeff')
    def test_snpeff(self):
        with self.preparation_stage():
            variants_lf = self.run_process('upload-variants-vcf', {'src': '56GSID_10k.lf.vcf'})
            dbsnp = self.run_process('upload-variants-vcf', {'src': 'dbsnp_138.b37.chr2_small.vcf.gz'})

        inputs = {
            'variants': variants_lf.id,
            'known_vars_annot': [dbsnp.id],
            'var_source': 'lofreq'
        }

        final_var_lf = self.run_process('snpeff', inputs)
        self.assertFile(final_var_lf, 'annotation', '56GSID.lf.finalvars.txt')
