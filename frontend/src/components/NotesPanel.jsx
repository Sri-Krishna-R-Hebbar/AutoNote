import { useEffect, useMemo, useRef, useState } from 'react';
import { Marked } from 'marked';
import DOMPurify from 'dompurify';

// Renders the notes markdown to HTML, tagging every H2/H3 heading with
// id="sec-N" in document order - this has to match the order the backend
// used when it built `sections`, so the two line up.
function renderMarkdown(markdownText) {
  let counter = 0;
  const marked = new Marked({
    renderer: {
      heading(token) {
        const inner = this.parser.parseInline(token.tokens);
        if (token.depth === 2 || token.depth === 3) {
          counter += 1;
          return `<h${token.depth} id="sec-${counter}">${inner}</h${token.depth}>\n`;
        }
        return `<h${token.depth}>${inner}</h${token.depth}>\n`;
      },
    },
  });
  const html = marked.parse(markdownText || '');
  return DOMPurify.sanitize(html);
}

export default function NotesPanel({ markdown, activeSectionId }) {
  const html = useMemo(() => renderMarkdown(markdown), [markdown]);
  const containerRef = useRef(null);
  const [follow, setFollow] = useState(true);

  useEffect(() => {
    if (!follow || !activeSectionId || !containerRef.current) return;
    const el = containerRef.current.querySelector(`#${activeSectionId}`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [activeSectionId, follow]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    container.querySelectorAll('h2[id], h3[id]').forEach((el) => {
      el.classList.toggle('notes-active-heading', el.id === activeSectionId);
    });
  }, [activeSectionId, html]);

  return (
    <div className="notes-panel">
      <label className="follow-toggle">
        <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} />
        Follow along with video
      </label>
      <div
        ref={containerRef}
        className="notes-markdown"
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}
