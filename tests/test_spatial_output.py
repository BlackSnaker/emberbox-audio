import json,sys,unittest
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from spatial_output import classify,inspect_output


def sink(index=1,name='test-pair',kind='Speaker',**properties):
    return {'index':index,'name':name,'description':'Test pair','sample_specification':'s16le 2ch 48000Hz',
            'properties':properties,'active_port':'out','ports':[{'name':'out','type':kind}]}


class OutputTests(unittest.TestCase):
    def test_physical_type_and_bluetooth_transport_are_distinct(self):
        s=sink(name='bluez_output.mock.1',kind='Headphones',**{'device.bus':'bluetooth','api.bluez5.codec':'sbc'})
        output=classify(s)
        self.assertEqual(output['kind'],'headphones') # A manual speaker override belongs to this hashed device.
        self.assertTrue(output['bluetooth']);self.assertEqual(output['rate'],48000)
        self.assertEqual(output['codec'],'sbc');self.assertNotIn(s['name'],json.dumps(output))
        self.assertEqual(len(output['key']),32);self.assertEqual(classify(sink())['kind'],'speakers')

    def test_app_route_wins_over_the_system_default(self):
        values=[json.dumps([sink(1),sink(2,'app-headphones','Headphones')]),json.dumps([{'sink':2,'properties':{}}])]
        with patch('spatial_output.subprocess.run',side_effect=[Mock(stdout=v) for v in values]) as run,patch('spatial_output.matches',return_value=True):
            self.assertEqual(inspect_output(123)['kind'],'headphones');self.assertEqual(run.call_count,2)

    def test_ambiguous_and_karaoke_routes_do_not_select_another_output(self):
        for destinations,names in (([1,2],[sink(1),sink(2)]),([1],[sink(name='emberbox_karaoke_test')])):
            values=[json.dumps(names),json.dumps([{'sink':n,'properties':{}} for n in destinations])]
            with patch('spatial_output.subprocess.run',side_effect=[Mock(stdout=v) for v in values]),patch('spatial_output.matches',return_value=True):
                self.assertIsNone(inspect_output(123))
    def test_a_corked_browser_decoder_does_not_hide_the_live_native_destination(self):
        values=[json.dumps([sink(1),sink(2,'headphones','Headphones')]),json.dumps([
            {'sink':1,'corked':True,'properties':{}},{'sink':2,'corked':False,'properties':{}}])]
        with patch('spatial_output.subprocess.run',side_effect=[Mock(stdout=v) for v in values]),patch('spatial_output.matches',return_value=True):
            self.assertEqual(inspect_output(123)['kind'],'headphones')


if __name__=='__main__':unittest.main()
