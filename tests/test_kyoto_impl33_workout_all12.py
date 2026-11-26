import unittest
from diagnostics.kyoto_impl33_workout_all12 import discover, HOST
from diagnostics.kyoto_impl33_whitegreen_probe import inspect, SAMPLES
from diagnostics.kyoto_impl33_workout_binding import bind
from test_kyoto_impl33_workout_binding import case

class All12(unittest.TestCase):
    def test_discovery_no_guessed_or_offsite_urls(self):
        html=b'<a href="/race/20261122-kyoto-03/">3</a><a href="https://evil.example/race/20261122-kyoto-04/">4</a><a href="/race/20261129-kyoto-09/">9</a><a href="/race/20261122-kyoto-13/">13</a>'
        self.assertEqual(discover(html,'20261122'),{3:HOST+'/race/20261122-kyoto-03/'})
    def test_short_summary(self):
        args=list(case());args[0]=args[0].replace('<th>併せ馬</th>'.encode(),b'').replace('<td>単走</td>'.encode(),b'')
        r,_=bind(*args);self.assertTrue(r['independent_roster_verified']);self.assertTrue(r['horse_history_binding_verified']);self.assertEqual(r['bound_dated_records'],2)
    def test_observed_identity(self):
        raw,day,race,url,stamp,*_=case()
        u=HOST+'/race/20261122-kyoto-02/';raw=raw.replace('京都1R'.encode(),'京都2R'.encode())
        with self.assertRaises(ValueError):inspect(raw,day,2,u,stamp)
        self.assertEqual(inspect(raw,day,2,u,stamp,((day,2,u),))['race'],2)
        with self.assertRaises(ValueError):inspect(raw,day,2,u+'x',stamp,((day,2,u+'x'),))
if __name__=='__main__':unittest.main()
