"""Create editable sharing artwork; export it to PNG before the website build."""
import base64
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
ASSETS=ROOT/'website/src/assets'


def main():
    encoded=base64.b64encode((ASSETS/'overview-dark.svg').read_bytes()).decode('ascii')
    svg='''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
<defs><radialGradient id="glow"><stop stop-color="#304976" stop-opacity=".45"/><stop offset="1" stop-color="#080b10" stop-opacity="0"/></radialGradient><linearGradient id="title"><stop stop-color="#91beff"/><stop offset=".55" stop-color="#d7d0ff"/><stop offset="1" stop-color="#98dbcf"/></linearGradient><linearGradient id="logo"><stop stop-color="#3474c5"/><stop offset="1" stop-color="#173b6d"/></linearGradient><pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="#80a9ef" stroke-opacity=".035"/></pattern><clipPath id="app"><rect width="710" height="433" rx="12"/></clipPath></defs>
<rect width="1200" height="630" fill="#080b10"/><ellipse cx="920" cy="300" rx="620" ry="400" fill="url(#glow)"/><rect width="1200" height="630" fill="url(#grid)"/>
<g font-family="Segoe UI,Arial,sans-serif"><rect x="70" y="65" width="44" height="44" rx="13" fill="url(#logo)" stroke="#6a93c5" stroke-opacity=".4"/><text x="92" y="97" text-anchor="middle" fill="#dbecff" font-size="31" font-weight="600">P</text><text x="127" y="99" fill="#eff5ff" font-size="34" font-weight="600" letter-spacing="-1.7">pulse<tspan fill="#83b6ff">.</tspan></text>
<rect x="972" y="74" width="158" height="29" rx="15" fill="#172335" stroke="#3d577a" stroke-opacity=".5"/><circle cx="990" cy="88.5" r="3" fill="#8adfca"/><text x="1003" y="92" fill="#a9c4e7" font-size="10" letter-spacing="1.2">FOR WINDOWS</text>
<text x="73" y="192" fill="#7794b9" font-size="11" letter-spacing="2.4">A CLEARER PICTURE OF YOUR LAPTOP</text>
<text x="66" y="286" fill="#f0f5ff" font-size="77" font-weight="600" letter-spacing="-4">Your laptop.</text><text x="66" y="374" fill="url(#title)" font-size="77" font-weight="600" letter-spacing="-4">In full focus.</text>
<text x="73" y="430" fill="#92a8c4" font-size="19">Performance. Storage. Clarity.</text><text x="73" y="462" fill="#7b95b6" font-size="17">One beautiful dashboard. Your data stays local.</text>
<rect x="72" y="516" width="163" height="42" rx="9" fill="#bfd8ff"/><text x="153.5" y="542" text-anchor="middle" fill="#183350" font-size="13" font-weight="600">Download Pulse ↓</text><text x="256" y="542" fill="#7290b6" font-size="13">pulse.infyss.com</text></g>
<g transform="translate(646 167) rotate(-5)"><rect x="-6" y="-6" width="722" height="445" rx="16" fill="#121e30" stroke="#709dd1" stroke-opacity=".3"/><image width="710" height="433" clip-path="url(#app)" href="data:image/svg+xml;base64,'''+encoded+'''"/></g>
</svg>'''
    (ASSETS/'social.svg').write_text(svg,encoding='utf-8')
    print('Sharing artwork ready: website/src/assets/social.svg (1200 x 630).')


if __name__=='__main__':main()
