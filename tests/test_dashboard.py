"""Dashboard-only regressions against frozen local evidence (no scientific reruns)."""
import json
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGES = ['Overview', 'Map', 'Monitor', 'Impact', 'Detect', 'Research & Method', 'Evidence & Sources']


def no_network(*args, **kwargs):
    raise AssertionError('Dashboard attempted a network connection')


class DashboardTests(unittest.TestCase):
    def app(self, page):
        at = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()
        at.radio[0].set_value(page).run()
        self.assertFalse(at.exception, [e.message for e in at.exception])
        self.assertFalse(at.error)
        return at

    def test_all_pages_local_analysis_with_osm_context(self):
        with patch.object(socket.socket, 'connect', no_network):
            for page in PAGES:
                with self.subTest(page=page):
                    at = self.app(page)
                    self.assertEqual(list(at.radio[0].options), PAGES)
                    for chart in at.get('deck_gl_json_chart'):
                        deck = json.loads(chart.proto.json)
                        self.assertEqual(deck['mapProvider'], 'carto')
                        self.assertTrue(deck['mapStyle'].startswith('https://basemaps.cartocdn.com/'))
                        self.assertNotIn('http', json.dumps(deck['layers']).lower())
                        self.assertFalse(chart.proto.mapbox_token)
                        for layer in deck['layers']:
                            if layer['@@type'] == 'TextLayer':
                                self.assertEqual(layer['getTextAnchor'], 'middle')
                                self.assertEqual(layer['getAlignmentBaseline'], 'center')

    def test_reference_separation(self):
        at = self.app('Research & Method')
        charts = [json.loads(c.proto.spec) for c in at.get('plotly_chart')]
        self.assertEqual(len(charts), 2)
        self.assertEqual(charts[0]['data'][0]['y'], ['RF v1', 'Final RF v2'])
        self.assertEqual(charts[1]['data'][0]['y'], ['Simple SAR', 'Lee SAR', 'Multisource', 'RF v1', 'Final RF v2'])
        values = {m.label: m.value for m in at.metric}
        self.assertEqual(values['Final RF · primary median IoU'], '0.353')
        self.assertEqual(values['Final RF · primary median F1'], '0.522')
        self.assertIn('0.489', values.values())
        self.assertIn('0.542', values.values())

    def test_monitor_and_later_total_water_evidence(self):
        at = self.app('Monitor')
        values = [m.value for m in at.metric]
        self.assertIn('1,026.80 ha', values)
        self.assertIn('993.52 ha', values)
        self.assertIn('33.28 ha', values)
        figure = json.loads(at.get('plotly_chart')[0].proto.spec)
        self.assertFalse(figure['layout']['dragmode'])
        self.assertTrue(figure['layout']['xaxis']['fixedrange'])
        self.assertTrue(any(len(trace['x']) == 7 for trace in figure['data']))
        self.assertTrue(any(trace.get('yaxis') == 'y2' for trace in figure['data']))
        at = self.app('Evidence & Sources')
        recovery = json.loads((ROOT / 'data/processed/phase4/recovery_validation.json').read_text())
        values = {m.label: m.value for m in at.metric}
        for label, field in [('Precision', 'precision'), ('Recall', 'recall'), ('F1', 'F1'), ('IoU', 'IoU')]:
            self.assertEqual(values[label], f"{recovery['metrics'][field]:.3f}")
        self.assertTrue(any('6.20 days later' in c.value and 'Not same-day' in c.value for c in at.caption))

    def test_one_scrubber_and_finite_player(self):
        at = self.app('Map')
        self.assertEqual(len(at.select_slider), 1)
        self.assertFalse(at.session_state['acquisition-player-playing'])
        at.select_slider[0].set_value(2).run()
        self.assertFalse(at.exception)
        self.assertTrue(any('OBS03' in m.value and '50.72 ha' in m.value for m in at.markdown))
        at.button(key='acquisition-player-play').click().run()
        self.assertTrue(at.session_state['acquisition-player-playing'])
        self.assertTrue(at.select_slider[0].disabled)
        at.session_state['acquisition-player-index'] = 6
        at.run()
        self.assertFalse(at.session_state['acquisition-player-playing'])
        self.assertEqual(at.select_slider[0].value, 6)
        self.assertTrue(any('Paused at 7 of 7' in m.value for m in at.markdown))
        at.button(key='acquisition-player-reset').click().run()
        self.assertEqual(at.select_slider[0].value, 0)

    def test_three_impact_lenses_keep_one_map(self):
        at = self.app('Impact')
        for lens in ['Infrastructure', 'Agricultural land', 'Community context']:
            at.button_group(key='impact-lens').set_value(lens).run()
            self.assertFalse(at.exception)
            self.assertEqual(len(at.get('deck_gl_json_chart')), 1)
        at.button_group(key='impact-lens').set_value('Infrastructure').run()
        self.assertTrue(any('234 AOI-clipped ways' in c.value for c in at.caption))
        self.assertEqual(len(at.dataframe[0].value), 14)


if __name__ == '__main__':
    unittest.main()
