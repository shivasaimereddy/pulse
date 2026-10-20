"""Generate editable 1200 × 630 sharing artwork from the public demo capture.

Export social.svg to social.png after changing the artwork. The website builder
fingerprints the PNG so sharing previews receive a fresh URL.
"""
import base64
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
ASSETS=ROOT/'website/src/assets'

def main():
    encoded=base64.b64encode((ASSETS/'screens/overview-dark.jpg').read_bytes()).decode('ascii')
    svg='''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
<defs><linearGradient id="logo" x2="1" y2="1"><stop stop-color="#b0b2ff"/><stop offset="1" stop-color="#7161df"/></linearGradient><radialGradient id="glow"><stop stop-color="#514883" stop-opacity=".4"/><stop offset="1" stop-color="#080b10" stop-opacity="0"/></radialGradient><clipPath id="screen"><rect x="650" y="147" width="650" height="470" rx="16"/></clipPath></defs>
<rect width="1200" height="630" fill="#080b10"/><ellipse cx="950" cy="400" rx="650" ry="450" fill="url(#glow)"/>
<g font-family="Segoe UI,Arial,sans-serif"><rect x="64" y="55" width="40" height="44" rx="11" fill="url(#logo)"/><text x="84" y="86" text-anchor="middle" fill="white" font-size="28" font-weight="600">P</text><text x="117" y="87" fill="#f1f2fa" font-size="32" font-weight="600" letter-spacing="-1.5">pulse<tspan fill="#a8a0ff">.</tspan></text>
<text x="64" y="166" fill="#a8a0ff" font-size="11" letter-spacing="2.2">YOUR WINDOWS PC. UNDERSTOOD.</text>
<text x="59" y="264" fill="#f1f2fa" font-size="79" font-weight="600" letter-spacing="-4">Your PC.</text><text x="59" y="353" fill="#b5acff" font-size="79" font-weight="600" letter-spacing="-4">In full focus.</text>
<text x="64" y="414" fill="#afb6cb" font-size="20">Live performance. Storage exploration.</text><text x="64" y="446" fill="#afb6cb" font-size="20">Local history. A clearer next step.</text>
<rect x="64" y="503" width="199" height="46" rx="9" fill="#bcb4ff"/><text x="163" y="532" text-anchor="middle" fill="#17122d" font-size="14" font-weight="600">Download for Windows ↓</text><text x="64" y="591" fill="#818aa3" font-size="13">pulse.infyss.com · Free download · Windows x64</text>
<rect x="641" y="138" width="667" height="488" rx="23" fill="#171c29" stroke="#797399"/><image x="650" y="147" width="650" height="625" clip-path="url(#screen)" href="data:image/jpeg;base64,'''+encoded+'''"/><rect x="804" y="548" width="292" height="31" rx="6" fill="#10141f" stroke="#34384d"/><text x="950" y="568" fill="#b9bfd0" font-size="10" text-anchor="middle">ACTUAL INTERFACE · ILLUSTRATIVE SAMPLE DATA</text></g></svg>'''
    (ASSETS/'social.svg').write_text(svg,encoding='utf-8')
    print('Sharing artwork ready: website/src/assets/social.svg (1200 x 630).')

if __name__=='__main__':main()
