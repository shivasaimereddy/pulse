"""Generate privacy-safe vector product previews. All displayed data is illustrative."""
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / 'website' / 'src' / 'assets'


def preview(view, dark=False):
    dark = dark or view == 'storage'
    bg, panel, sidebar = ('#141519', '#202126', '#1b1c22') if dark else ('#f5f5f7', '#ffffff', '#edeef2')
    ink, muted, line, blue = ('#f0f3f8', '#9ba9bc', '#353b47', '#79b8ff') if dark else ('#202734', '#8a96a7', '#e6eaf0', '#0071e3')
    items = []

    def rect(x, y, w, h, fill=panel, radius=12, stroke=None):
        items.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}"'+(f' stroke="{stroke}"' if stroke else '')+'/>')

    def text(x, y, content, size=14, color=ink, weight=400, anchor='start'):
        items.append(f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">{escape(str(content))}</text>')

    def path(d, color=blue, width=2, fill='none'):
        items.append(f'<path d="{d}" fill="{fill}" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>')

    def rule(x1, y, x2):
        path(f'M{x1} {y}H{x2}', line, 1)

    def chart(x, y, w, h, sequence, color, fill=False):
        points=[(x+i*w/(len(sequence)-1),y+h-v*h/100) for i,v in enumerate(sequence)]
        d='M'+' L'.join(f'{px:.1f} {py:.1f}' for px,py in points)
        if fill:
            path(d+f' L{x+w} {y+h} L{x} {y+h}Z','none',0,color+'0d')
        path(d,color,2)

    rect(0,0,1280,780,bg,0)
    rect(0,0,205,780,sidebar,0)
    rect(25,26,30,30,'url(#brand)',9)
    text(40,48,'P',22,'white',650,'middle');text(65,48,'Pulse',23,ink,650)
    text(26,103,'YOUR LAPTOP',9,muted,600)
    nav=[('overview','Overview','grid'),('apps','Apps & processes','apps'),('storage','Storage','disk'),('changes','Storage changes','changes'),('history','Performance history','chart'),('improve','Improve performance','spark'),('about','About Pulse','about')]
    for i,(key,label,shape) in enumerate(nav):
        y=135+i*43
        active=key==view
        if active:rect(14,y-20,177,36,'#303a4a' if dark else '#fff',8)
        c=blue if active else muted
        if shape=='grid':
            for px,py in [(29,y-8),(38,y-8),(29,y+1),(38,y+1)]:rect(px,py,6,6,c,1)
        elif shape=='disk':
            rect(29,y-7,15,12,'none',2,c);path(f'M29 {y+1}H44',c,1)
        elif shape=='chart':path(f'M29 {y-9}V{y+7}H45M32 {y+2}l4-5 4 3 5-8',c,1.4)
        elif shape=='spark':path(f'M37 {y-9}l2 6 6 2-6 2-2 6-2-6-6-2 6-2Z',c,1.4)
        elif shape=='about':
            items.append(f'<circle cx="37" cy="{y-1}" r="7" fill="none" stroke="{c}" stroke-width="1.4"/>');text(37,y+3,'i',11,c,500,'middle')
        else:
            rect(30,y-9,13,16,'none',2,c);path(f'M34 {y-4}H39M34 {y}H39',c,1.3)
        text(55,y+3,label,11,c,550 if active else 400)
    rule(23,704,182);rect(25,727,25,25,'#dde5ef' if not dark else '#283444',7)
    text(64,737,'Your laptop',11,ink,550);text(64,753,'Connected locally',9,muted)
    text(238,37,dict(overview='Overview',apps='Apps & processes',storage='Storage',history='Performance history')[view],12,muted,500)
    text(1190,37,'Live · every 2 seconds',10,muted,400,'end');items.append(f'<circle cx="1070" cy="33" r="3" fill="#41a984"/>')
    rect(1205,23,48,23,panel,6,line);text(1229,38,'Pause',9,muted,400,'middle')
    rule(238,57,1253)
    title=dict(overview='A clearer picture.',apps='Apps & processes',storage='Space for what’s next.',history='Performance history')[view]
    text(238,111,title,35,ink,600)
    subtitle=dict(overview='Understand what’s happening. Know what to do next.',apps='Identify scripts, inspect resource usage, and take informed action.',storage='Find large folders. Review your files. Reclaim space thoughtfully.',history='Review processor, memory, network, battery, and free-space trends.')[view]
    text(239,140,subtitle,12,muted)
    if view=='overview':
        rect(238,170,1015,64,'#1c2c40' if dark else '#edf4fd',12)
        rect(255,186,32,32,'#253e5b' if dark else '#e0edff',10);text(271,208,'✓',19,blue,500,'middle')
        text(303,196,'A little clarity goes a long way.',14,ink,550);text(303,216,'Your essential readings, together in one place.',11,muted)
        text(1229,207,'See recommendations  →',10,blue,500,'end')
        metrics=[('Processor','18.2','%','Plenty of headroom',blue),('Memory','62.4','%','9.9 GB of 16 GB','#9475c8'),('Storage','67.1','%','328 GB free of 1 TB','#49a88b'),('Battery','86','%','Plugged in','#d5a35c')]
        seqs=[[22,24,17,29,21,33,20,27,18,22,17,28,19,21,18],[53,55,54,57,59,60,59,62,61,60,63,62,62,63,62],[67]*15,[71,72,73,74,75,75,76,78,79,80,81,83,84,85,86]]
        for i,(name,value,unit,detail,c) in enumerate(metrics):
            x=238+i*258
            rect(x,254,241,193,panel,12,line)
            rect(x+17,272,25,25,c+'16',8);text(x+29.5,290,['⌘','≡','▱','ϟ'][i],15,c,500,'middle')
            text(x+52,288,name,11,muted,500);text(x+18,343,value,38,ink,600);text(x+110,341,unit,18,muted)
            chart(x+18,365,204,38,seqs[i],c,True);text(x+18,429,detail,10,muted)
        rect(238,468,661,270,panel,12,line);text(259,497,'Activity, at a glance',15,ink,550);text(873,496,'CPU  /  MEMORY',8,muted,500,'end')
        for y in [536,587,638,689]:rule(278,y,876)
        for y,v in [(539,'100%'),(590,'50%'),(692,'0%')]:text(257,y,v,8,muted)
        chart(287,527,588,159,[18,21,19,22,35,21,38,28,22,21,23,18,25,17,18,22,18],blue,True)
        chart(287,527,588,159,[56,58,57,60,59,62,63,61,62,64,62,60,63,64,62,63,62],'#a184c8')
        text(286,717,'2 minutes ago',9,muted);text(873,717,'Now',9,muted,400,'end')
        rect(920,468,333,270,panel,12,line);text(941,497,'Your essentials',15,ink,550)
        for i,(name,v,detail) in enumerate([('Network','2.4 MB/s','Download · 460 KB/s upload'),('Uptime','3h 42m','Since your last restart'),('Top app','Visual Studio Code','8.3% CPU · 942 MB memory')]):
            y=529+i*70
            if i:rule(942,y-17,1231)
            text(942,y,name,10,muted);text(1230,y,v,12,ink,550,'end');text(942,y+20,detail,9,muted)
    elif view=='apps':
        for i,(name,value,detail) in enumerate([('Running processes','148','Grouped into 32 apps'),('Processor in use','24.7%','Share of all processors'),('Memory in use','9.9 GB','Of 16 GB installed')]):
            x=238+i*345;rect(x,175,326,100,panel,12,line);text(x+20,201,name,11,muted);text(x+20,242,value,29,ink,600);text(x+305,250,detail,9,muted,400,'end')
        rect(238,296,1015,443,panel,12,line);text(259,327,'What’s running',16,ink,550)
        rect(845,308,385,31,'#f6f8fb',7,line);text(860,328,'Search apps, scripts, or process IDs',10,muted)
        for i,(label,w) in enumerate([('All apps',63),('Heavy users',84),('Your apps',93)]):
            x=[259,333,428][i];rect(x,349,w,26,'#eaf2ff' if i==0 else '#f6f8fb',6);text(x+w/2,366,label,9,blue if i==0 else muted,400,'middle')
        for x,label in [(260,'APP / PROCESS GROUP'),(925,'PROCESSOR'),(1050,'MEMORY'),(1172,'INSPECT')]:text(x,411,label,8,muted,500)
        rows=[('Da','Data analysis','App group · 3 processes','18.2%','624 MB','#eaf2ff','#5a8acb'),('VS','Visual Studio Code','Code.exe · 12 processes','8.3%','942 MB','#e8f2fb','#5b8bab'),('E','Microsoft Edge','msedge.exe · 18 processes','4.1%','1.2 GB','#e4f4ef','#40957e'),('Ex','File Explorer','explorer.exe · 1 process','0.8%','148 MB','#fff5df','#bca157'),('P','Pulse monitor','Pulse.exe · Protected','0.3%','42 MB','#eef1fd','#778cc1')]
        for i,(badge,name,detail,cpu,mem,fill,c) in enumerate(rows):
            y=448+i*57;rule(260,y-17,1230);rect(260,y-4,30,30,fill,8);text(275,y+17,badge,11,c,600,'middle');text(305,y+6,name,12,ink,550);text(305,y+23,detail,9,muted);text(965,y+12,cpu,12,ink,500,'end');text(1095,y+12,mem,11,muted,400,'end');rect(1171,y-1,59,24,'#f2f5f9',6);text(1200,y+15,'Review ↗',9,blue,400,'middle')
    elif view=='storage':
        rect(238,170,1015,97,panel,12,line);text(259,198,'Windows (C:)',15,ink,550);text(1230,198,'671 GB used of 1 TB',11,muted,400,'end')
        rect(259,218,971,7,'#343c48',3);rect(259,218,652,7,'#6b9edc',3);text(259,248,'328 GB available',10,muted);text(1230,248,'Windows disk · local storage',9,muted,400,'end')
        rect(238,287,1015,452,panel,12,line);text(260,319,'Explore your storage',16,ink,550);text(260,341,'Scan once. Browse folders instantly.',11,muted)
        rect(260,359,831,34,'#191c22',7,line);text(277,381,'Documents',12,ink);text(1070,381,'⌄',12,muted);rect(1105,359,125,34,'#2789f2',7);text(1167,381,'Scan again',11,'white',550,'middle')
        text(260,416,'Saved scan · Today, 10:42 AM',10,muted);text(260,445,'24.8 GB',16,ink,550);text(338,444,'in listed items',10,muted);text(460,445,'12,480',15,ink,550);text(521,444,'files checked',10,muted)
        for x,w,c in [(260,505,'#65a6eb'),(767,234,'#ae98d3'),(1003,119,'#6aac9f'),(1124,70,'#d8ba82'),(1196,34,'#818da7')]:rect(x,463,w,8,c,1)
        rule(260,492,1230);text(260,519,'↑ Up',10,blue);text(315,519,'C:\\Users\\You\\Documents',11,muted);text(1228,519,'Open in Explorer ↗',10,blue,400,'end')
        rect(260,537,208,29,'#171b21',7);rect(264,541,112,21,'#394250',5);text(320,555,'Folder contents',9,ink,500,'middle');text(422,555,'Largest files',9,muted,400,'middle')
        text(1228,555,'Filter & sort',9,blue,400,'end')
        for i,(name,detail,size,c) in enumerate([('Projects','Folder · 8,240 files','12.9 GB','#65a6eb'),('Design assets','Folder · 2,804 files','6.0 GB','#ae98d3'),('Archive','Folder · 1,428 files','3.1 GB','#6aac9f')]):
            y=598+i*48;rect(260,y-9,26,26,c+'20',7);text(273,y+9,'▰',14,c,500,'middle');text(301,y+1,name,12,ink,550);text(301,y+17,detail,9,muted);text(1230,y+7,size,12,ink,500,'end');rule(300,y+30,1230)
    else:
        for i,name in enumerate(['1 hour','24 hours','7 days','30 days','1 year']):
            x=238+i*77;rect(x,173,70,29,'white' if i==1 else '#e9edf2',6);text(x+35,192,name,10,ink if i==1 else muted,500,'middle')
        text(1231,192,'Refresh history ↻',10,blue,400,'end');text(239,227,'A little perspective on your laptop’s activity.',11,muted)
        for i,(name,value,detail) in enumerate([('Average processor','21.4%','Peak 78.2%'),('Average memory','58.7%','Peak 74.1%'),('Free space change','+2.4 GB','Across saved readings')]):
            x=238+i*345;rect(x,248,326,107,panel,12,line);text(x+21,276,name,11,muted);text(x+21,319,value,29,ink,600);text(x+305,334,detail,9,muted,400,'end')
        rect(238,376,1015,363,panel,12,line);text(259,406,'The shape of your day',16,ink,550);text(1230,405,'Processor & memory',10,muted,400,'end');text(259,430,'Minute averages · gaps reflect missing readings',10,muted)
        for y in [468,526,584,642]:rule(290,y,1226)
        for y,value in [(471,'100%'),(529,'66%'),(587,'33%'),(645,'0%')]:text(259,y,value,9,muted)
        chart(294,468,932,173,[13,14,18,16,22,19,15,21,36,28,18,19,22,17,21,28,45,66,59,78,65,55,29,18,17,23,19,26,24,29,22,18,20,21,24,20,17,21,19,18],blue,True)
        chart(294,468,932,173,[45,46,45,47,49,48,49,50,51,53,51,52,54,55,56,57,59,61,64,65,67,68,66,64,63,61,62,59,58,57,56,57,56,58,59,58,57,58,58,59],'#a184c8')
        for i,label in enumerate(['12 AM','6 AM','12 PM','6 PM','Now']):text(296+i*231,673,label,9,muted)
        text(260,715,'●  Processor',9,blue);text(364,715,'●  Memory',9,'#a184c8');text(1230,715,'Saved locally on your laptop',9,muted,400,'end')
    text(239,766,'Pulse · Your laptop, understood.',8,muted);text(1251,766,'Illustrative sample data',8,muted,400,'end')
    return '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="780" viewBox="0 0 1280 780"><defs><linearGradient id="brand" x2="1" y2="1"><stop stop-color="#58b0ff"/><stop offset="1" stop-color="#0071e3"/></linearGradient></defs><g font-family="Segoe UI,Arial,sans-serif">'+''.join(items)+'</g></svg>'


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / 'overview-dark.svg').write_text(preview('overview', dark=True), encoding='utf-8')
    for view in ('overview','apps','storage','history'):
        (ASSETS / (view+'.svg')).write_text(preview(view), encoding='utf-8')
    (ASSETS / 'icon.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><defs><linearGradient id="b" x2="1" y2="1"><stop stop-color="#58b0ff"/><stop offset="1" stop-color="#0068e6"/></linearGradient></defs><rect width="64" height="64" rx="17" fill="url(#b)"/><text x="32" y="47" text-anchor="middle" font-size="44" font-weight="650" font-family="Segoe UI,Arial" fill="white">P</text></svg>', encoding='utf-8')
    from generate_social_preview import main as generate_social
    generate_social()
    print('Generated four privacy-safe product previews and brand assets.')


if __name__ == '__main__':
    main()
