import graphviz

def generate_mindmap_from_headings(headings: list) -> graphviz.Digraph:
    """
    Generates a cleaner, visually enhanced mindmap from list of headings.
    """

    dot = graphviz.Digraph(comment='SEO Brief Mindmap')

    # Global graph settings
    dot.attr(rankdir='TB')  # Top to Bottom flow
    dot.attr('node', shape='box', style='filled', color='lightgrey', fontname='Helvetica')
    dot.attr('edge', arrowhead='vee', color='grey')

    last_h1 = None
    last_h2 = None

    for heading in headings:
        if heading.startswith("H1:"):
            h1_text = heading.replace("H1:", "").strip()
            dot.node(h1_text, shape='rectangle', style='filled', color='lightblue')
            last_h1 = h1_text
        elif heading.startswith("H2:") and last_h1:
            h2_text = heading.replace("H2:", "").strip()
            dot.node(h2_text, shape='ellipse', style='filled', color='lightgreen')
            dot.edge(last_h1, h2_text)
            last_h2 = h2_text
        elif heading.startswith("H3:") and last_h2:
            h3_text = heading.replace("H3:", "").strip()
            dot.node(h3_text, shape='oval', style='filled', color='lightyellow')
            dot.edge(last_h2, h3_text)
        elif heading.startswith("H4:") and last_h2:
            h4_text = heading.replace("H4:", "").strip()
            dot.node(h4_text, shape='note', style='filled', color='white')
            dot.edge(last_h2, h4_text)

    return dot
