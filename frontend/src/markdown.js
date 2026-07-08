/**
 * Lightweight Markdown → HTML renderer for chat bubbles.
 * Handles: headings, bold, italic, inline code, code blocks,
 * tables, ordered/unordered lists, and line breaks.
 *
 * No external dependencies — pure string transforms.
 */

export function renderMarkdown(text) {
  if (!text) return ''

  let html = text

  // 1. Escape HTML entities first (prevent XSS)
  html = html
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // 2. Code blocks (``` ... ```)  — must come before inline transforms
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_m, _lang, code) => {
    return `<pre class="md-code-block"><code>${code.trim()}</code></pre>`
  })

  // 3. Tables — detect lines with pipes
  html = processMarkdownTables(html)

  // 4. Headings (### → h3, ## → h2, # → h1)
  html = html.replace(/^#### (.+)$/gm, '<h4 class="md-h4">$1</h4>')
  html = html.replace(/^### (.+)$/gm, '<h3 class="md-h3">$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2 class="md-h2">$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1 class="md-h1">$1</h1>')

  // 5. Bold + Italic  (**text** and *text*)
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')

  // 6. Inline code (`code`)
  html = html.replace(/`([^`]+)`/g, '<code class="md-inline-code">$1</code>')

  // 7. Horizontal rule
  html = html.replace(/^---+$/gm, '<hr class="md-hr"/>')

  // 8. Ordered lists (1. 2. 3.)
  html = html.replace(/^(\d+)\.\s+(.+)$/gm, '<li class="md-ol-item" value="$1">$2</li>')
  html = html.replace(/((?:<li class="md-ol-item"[^>]*>.*?<\/li>\n?)+)/g, '<ol class="md-ol">$1</ol>')

  // 9. Unordered lists (- or * at start of line)
  html = html.replace(/^[\-\*]\s+(.+)$/gm, '<li class="md-ul-item">$1</li>')
  html = html.replace(/((?:<li class="md-ul-item">.*?<\/li>\n?)+)/g, '<ul class="md-ul">$1</ul>')

  // 10. Nested list items (indented with spaces)
  html = html.replace(/^\s{2,}[\-\*]\s+(.+)$/gm, '<li class="md-ul-nested">$1</li>')

  // 11. Line breaks — convert double newline to paragraph break, single to <br>
  //     But skip inside <pre>, <ol>, <ul>, <table> blocks
  html = html.replace(/\n{2,}/g, '</p><p class="md-p">')
  html = html.replace(/\n/g, '<br/>')

  // Wrap in paragraph
  html = `<p class="md-p">${html}</p>`

  // Clean up empty paragraphs
  html = html.replace(/<p class="md-p"><\/p>/g, '')
  html = html.replace(/<p class="md-p">(<h[1-4])/g, '$1')
  html = html.replace(/(<\/h[1-4]>)<\/p>/g, '$1')
  html = html.replace(/<p class="md-p">(<(?:ol|ul|pre|table|hr))/g, '$1')
  html = html.replace(/(<\/(?:ol|ul|pre|table)>)<\/p>/g, '$1')
  html = html.replace(/<br\/>(<(?:ol|ul|pre|table|h[1-4]|hr))/g, '$1')
  html = html.replace(/(<\/(?:ol|ul|pre|table|h[1-4])>)<br\/>/g, '$1')

  return html
}


/**
 * Process markdown tables into HTML <table> elements.
 */
function processMarkdownTables(text) {
  const lines = text.split('\n')
  const result = []
  let inTable = false
  let tableRows = []

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()

    // Detect table row: starts and ends with | or contains multiple |
    const isTableRow = line.startsWith('|') && line.endsWith('|') && line.split('|').length >= 3
    // Detect separator row: |---|---|
    const isSeparator = /^\|[\s\-:]+(\|[\s\-:]+)+\|$/.test(line)

    if (isTableRow || isSeparator) {
      if (!inTable) {
        inTable = true
        tableRows = []
      }
      if (!isSeparator) {
        // Parse cells
        const cells = line.split('|').slice(1, -1).map(c => c.trim())
        tableRows.push(cells)
      }
    } else {
      if (inTable) {
        // Flush table
        result.push(buildTable(tableRows))
        inTable = false
        tableRows = []
      }
      result.push(lines[i])
    }
  }

  // Flush trailing table
  if (inTable) {
    result.push(buildTable(tableRows))
  }

  return result.join('\n')
}


function buildTable(rows) {
  if (rows.length === 0) return ''
  const [header, ...body] = rows
  let html = '<table class="md-table"><thead><tr>'
  header.forEach(cell => {
    html += `<th>${cell}</th>`
  })
  html += '</tr></thead><tbody>'
  body.forEach(row => {
    html += '<tr>'
    row.forEach(cell => {
      html += `<td>${cell}</td>`
    })
    html += '</tr>'
  })
  html += '</tbody></table>'
  return html
}
