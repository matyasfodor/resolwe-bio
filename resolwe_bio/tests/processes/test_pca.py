# pylint: disable=missing-docstring
import six

from resolwe.test import tag_process
from resolwe_bio.utils.test import BioProcessTestCase


class PcaProcessorTestCase(BioProcessTestCase):

    @tag_process('pca')
    def test_pca(self):
        with self.preparation_stage():
            expression_1 = self.prepare_expression(f_rc='exp_1_rc.tab.gz',
                                                   f_exp='exp_1_tpm.tab.gz',
                                                   f_type='TPM',
                                                   source='DICTYBASE')
            expression_2 = self.prepare_expression(f_rc='exp_2_rc.tab.gz',
                                                   f_exp='exp_2_tpm.tab.gz',
                                                   f_type='TPM',
                                                   source='DICTYBASE')

        inputs = {'exps': [expression_1.pk, expression_2.pk], 'genes_source': 'DICTYBASE'}
        pca = self.run_process('pca', inputs)
        saved_json, test_json = self.get_json('pca_plot.json.gz', pca.output['pca'])
        self.assertAlmostEqualGeneric(test_json['flot']['data'], saved_json['flot']['data'])
        self.assertAlmostEqualGeneric(test_json['explained_variance_ratios'], saved_json['explained_variance_ratios'])
        self.assertAlmostEqualGeneric(test_json['components'], saved_json['components'])
        self.assertEqual(len(pca.process_warning), 0)

        inputs = {
            'exps': [expression_1.pk, expression_2.pk],
            'genes': ['DPU_G0067098', 'DPU_G0067100', 'DPU_G0067104'],  # all zero
            'genes_source': 'DICTYBASE'
        }
        pca = self.run_process('pca', inputs)
        self.assertEqual(len(pca.process_warning), 1)
        self.assertEqual(
            pca.process_warning[0],
            'Gene selection and filtering resulted in no genes. Please select different samples or genes.'
        )

    @tag_process('pca')
    def test_pca_ncbi(self):
        with self.preparation_stage():
            expression_1 = self.prepare_expression(f_exp='clustering_NCBI.gz',
                                                   f_type='rc',
                                                   name='Expression',
                                                   source='NCBI')
            expression_2 = self.prepare_expression(f_exp='clustering_NCBI_1.gz',
                                                   f_type='rc',
                                                   name='Expression',
                                                   source='NCBI')
            expression_3 = self.prepare_expression(f_exp='clustering_NCBI_2.gz',
                                                   f_type='rc',
                                                   name='Expression',
                                                   source='NCBI')

        inputs = {'exps': [expression_1.pk, expression_2.pk, expression_3.pk, ],
                  'genes': ['1', '503538', '56934', '29974', '2', '144571', '3', 'abc', 'lll'],
                  'genes_source': 'NCBI'}
        pca = self.run_process('pca', inputs)
        saved_json, test_json = self.get_json('pca_plot_ncbi.json.gz', pca.output['pca'])
        six.assertCountEqual(self, test_json['zero_gene_symbols'], saved_json['zero_gene_symbols'])
