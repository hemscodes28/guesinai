with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

from html.parser import HTMLParser

class DivTracker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        
    def handle_starttag(self, tag, attrs):
        if tag in ('div', 'footer'):
            attrs_dict = dict(attrs)
            tag_id = attrs_dict.get('id')
            tag_class = attrs_dict.get('class')
            self.stack.append((tag, tag_id, tag_class, self.getpos()))
            print(f'Line {self.getpos()[0]}: Opened <{tag} id={tag_id} class={tag_class}>. Stack size: {len(self.stack)}')
            
    def handle_endtag(self, tag):
        if tag in ('div', 'footer'):
            if not self.stack:
                print(f'Line {self.getpos()[0]}: Unexpected </{tag}>. Stack empty!')
                return
            start_tag, start_id, start_class, start_pos = self.stack.pop()
            print(f'Line {self.getpos()[0]}: Closed </{tag}> (matched <{start_tag} id={start_id} class={start_class}> from line {start_pos[0]}). Stack size: {len(self.stack)}')

tracker = DivTracker()
lines = html.splitlines()
tracker.feed('\n'.join(lines[:1245]))
