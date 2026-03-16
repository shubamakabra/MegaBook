/**
 * ObsidianMarkdown — A ReactMarkdown wrapper that handles Obsidian-flavored
 * markdown syntax: wiki-links, image/audio/video/PDF embeds with size
 * specifiers, ==highlights==, %%comments%%, and callouts (> [!type]).
 *
 * All vault file references are routed through /api/filesystem/download/{path}.
 */
import React, { useMemo } from 'react';
import ReactMarkdown, { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import './ObsidianMarkdown.css';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const IMAGE_EXTENSIONS = new Set([
  '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.avif', '.ico',
]);
const AUDIO_EXTENSIONS = new Set([
  '.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac', '.webm', '.3gp',
]);
const VIDEO_EXTENSIONS = new Set(['.mp4', '.mkv', '.mov', '.ogv', '.webm']);
const PDF_EXTENSIONS = new Set(['.pdf']);

function extOf(filename: string): string {
  const dot = filename.lastIndexOf('.');
  return dot >= 0 ? filename.slice(dot).toLowerCase() : '';
}

// ---------------------------------------------------------------------------
// Pre-processing: string-level transforms BEFORE ReactMarkdown parses
// ---------------------------------------------------------------------------

/** Strip Obsidian `%%…%%` comments (inline and block). */
function stripComments(md: string): string {
  return md.replace(/%%[\s\S]*?%%/g, '');
}

/** Convert `==text==` highlights to `<mark>text</mark>`. Requires rehype-raw. */
function convertHighlights(md: string): string {
  return md.replace(/==(.*?)==/g, '<mark>$1</mark>');
}

/**
 * Convert Obsidian embed syntax `![[target]]` and `![[target|size]]` into
 * standard markdown / HTML that ReactMarkdown can render.
 *
 * Uses custom URI schemes (obsidian-vault://, obsidian-vault-audio://, etc.)
 * so the custom component overrides can rewrite them through the download API.
 */
function convertEmbeds(md: string): string {
  return md.replace(/!\[\[([^\]]+)\]\]/g, (_match, inner: string) => {
    const pipeIndex = inner.indexOf('|');
    const target = pipeIndex >= 0 ? inner.slice(0, pipeIndex).trim() : inner.trim();
    const sizeSpec = pipeIndex >= 0 ? inner.slice(pipeIndex + 1).trim() : '';
    const ext = extOf(target);

    if (IMAGE_EXTENSIONS.has(ext)) {
      const alt = sizeSpec ? `${target}|${sizeSpec}` : target;
      return `![${alt}](obsidian-vault://${encodeURIComponent(target)})`;
    }
    if (AUDIO_EXTENSIONS.has(ext)) {
      return `<audio controls src="obsidian-vault-audio://${encodeURIComponent(target)}"></audio>`;
    }
    if (VIDEO_EXTENSIONS.has(ext)) {
      return `<video controls src="obsidian-vault-video://${encodeURIComponent(target)}"></video>`;
    }
    if (PDF_EXTENSIONS.has(ext)) {
      return `\`📑 Embedded PDF: ${target}\``;
    }
    // Note embed — render as a styled placeholder
    return `> **📄 Embedded note:** [[${target}]]`;
  });
}

/**
 * Convert Obsidian wiki-links `[[target]]` and `[[target|display]]` into
 * standard markdown links with a custom URI scheme.
 */
function convertWikiLinks(md: string): string {
  return md.replace(/\[\[([^\]]+)\]\]/g, (_match, inner: string) => {
    const pipeIndex = inner.indexOf('|');
    const target = pipeIndex >= 0 ? inner.slice(0, pipeIndex).trim() : inner.trim();
    const display = pipeIndex >= 0 ? inner.slice(pipeIndex + 1).trim() : formatLinkDisplay(target);
    return `[${display}](obsidian-link://${encodeURIComponent(target)})`;
  });
}

/** Format a wiki-link target as display text: "Page#Heading" -> "Page > Heading" */
function formatLinkDisplay(target: string): string {
  if (target.startsWith('#')) {
    return target.slice(1).replace(/-/g, ' ');
  }
  return target.replace(/#\^?/g, ' > ');
}

/**
 * Convert Obsidian callouts into blockquotes with a hidden HTML comment marker
 * that the custom blockquote component can detect and style.
 */
function convertCallouts(md: string): string {
  const lines = md.split('\n');
  const result: string[] = [];
  let i = 0;

  while (i < lines.length) {
    const calloutMatch = lines[i].match(/^>\s*\[!(\w+)\]([+-])?\s*(.*)/);
    if (calloutMatch) {
      const type = calloutMatch[1].toLowerCase();
      const foldable = calloutMatch[2] || '';
      const title = calloutMatch[3] || type.charAt(0).toUpperCase() + type.slice(1);

      result.push(`> <!--callout:${type}:${foldable}:${title}-->`);
      i++;
      while (i < lines.length && (lines[i].startsWith('> ') || lines[i] === '>')) {
        result.push(lines[i]);
        i++;
      }
    } else {
      result.push(lines[i]);
      i++;
    }
  }

  return result.join('\n');
}

/** Full pre-processing pipeline. Order matters: callouts before embeds/links. */
function preprocessObsidian(md: string): string {
  let result = md;
  result = stripComments(result);
  result = convertCallouts(result);
  result = convertEmbeds(result);
  result = convertWikiLinks(result);
  result = convertHighlights(result);
  return result;
}

// ---------------------------------------------------------------------------
// URL resolution helpers
// ---------------------------------------------------------------------------

/** Get the directory portion of a vault-relative file path. */
function dirOf(filePath: string): string {
  const lastSlash = filePath.lastIndexOf('/');
  return lastSlash >= 0 ? filePath.slice(0, lastSlash) : '';
}

/**
 * Build a download URL for a vault-relative file path.
 * Filenames without directory components are resolved relative to the
 * current file's directory (matching Obsidian's "shortest path" behavior
 * for the common case of co-located attachments).
 */
function buildDownloadUrl(ref: string, currentFileDir: string): string {
  const decoded = decodeURIComponent(ref);

  let vaultPath: string;
  if (decoded.startsWith('/') || /^[a-zA-Z]:/.test(decoded)) {
    // Absolute path
    vaultPath = decoded;
  } else if (decoded.includes('/')) {
    // Has directory component — treat as vault-relative
    vaultPath = decoded;
  } else {
    // Just a filename — resolve relative to current file's directory
    vaultPath = currentFileDir ? `${currentFileDir}/${decoded}` : decoded;
  }

  return `${API_BASE}/api/filesystem/download/${encodeURIComponent(vaultPath)}`;
}

// ---------------------------------------------------------------------------
// Callout helpers
// ---------------------------------------------------------------------------

const CALLOUT_ICONS: Record<string, string> = {
  note: '\u2139\uFE0F', info: '\u2139\uFE0F',
  abstract: '\uD83D\uDCCB', summary: '\uD83D\uDCCB', tldr: '\uD83D\uDCCB',
  todo: '\u2611\uFE0F',
  tip: '\uD83D\uDCA1', hint: '\uD83D\uDCA1', important: '\uD83D\uDCA1',
  success: '\u2705', check: '\u2705', done: '\u2705',
  question: '\u2753', help: '\u2753', faq: '\u2753',
  warning: '\u26A0\uFE0F', caution: '\u26A0\uFE0F', attention: '\u26A0\uFE0F',
  failure: '\u274C', fail: '\u274C', missing: '\u274C',
  danger: '\uD83D\uDD34', error: '\uD83D\uDD34',
  bug: '\uD83D\uDC1B',
  example: '\uD83D\uDCCE',
  quote: '\uD83D\uDCAC', cite: '\uD83D\uDCAC',
};

const CALLOUT_COLORS: Record<string, string> = {
  note: '#448aff', info: '#448aff', todo: '#448aff',
  abstract: '#00bfa5', summary: '#00bfa5', tldr: '#00bfa5',
  tip: '#00bfa5', hint: '#00bfa5', important: '#00bfa5',
  success: '#00c853', check: '#00c853', done: '#00c853',
  question: '#ffab00', help: '#ffab00', faq: '#ffab00',
  warning: '#ff9100', caution: '#ff9100', attention: '#ff9100',
  failure: '#ff5252', fail: '#ff5252', missing: '#ff5252',
  danger: '#ff1744', error: '#ff1744',
  bug: '#ff5252',
  example: '#7c4dff',
  quote: '#9e9e9e', cite: '#9e9e9e',
};

// ---------------------------------------------------------------------------
// Custom ReactMarkdown component overrides
// ---------------------------------------------------------------------------

function createComponents(currentFileDir: string): Components {
  return {
    // Images: resolve vault paths through the download API, parse Obsidian size specifiers
    img: ({ src, alt, ...props }) => {
      if (!src) return <img alt={alt} {...props} />;

      let resolvedSrc = src;
      let width: number | undefined;
      let height: number | undefined;

      if (src.startsWith('obsidian-vault://')) {
        const ref = src.replace('obsidian-vault://', '');
        resolvedSrc = buildDownloadUrl(ref, currentFileDir);

        // Parse size from alt text: "filename|400" or "filename|400x300"
        if (alt && alt.includes('|')) {
          const parts = alt.split('|');
          const sizeStr = parts[parts.length - 1];
          const sizeMatch = sizeStr.match(/^(\d+)(?:x(\d+))?$/);
          if (sizeMatch) {
            width = parseInt(sizeMatch[1], 10);
            height = sizeMatch[2] ? parseInt(sizeMatch[2], 10) : undefined;
            alt = parts.slice(0, -1).join('|');
          }
        }
      } else if (!src.startsWith('http://') && !src.startsWith('https://') && !src.startsWith('data:')) {
        // Standard markdown image with relative/vault path
        resolvedSrc = buildDownloadUrl(src, currentFileDir);
      }

      // Parse Obsidian's external image size syntax: ![alt|WxH](url)
      if (alt && alt.includes('|') && !width) {
        const parts = alt.split('|');
        const sizeStr = parts[parts.length - 1];
        const sizeMatch = sizeStr.match(/^(\d+)(?:x(\d+))?$/);
        if (sizeMatch) {
          width = parseInt(sizeMatch[1], 10);
          height = sizeMatch[2] ? parseInt(sizeMatch[2], 10) : undefined;
          alt = parts.slice(0, -1).join('|');
        }
      }

      return (
        <img
          src={resolvedSrc}
          alt={alt || ''}
          width={width}
          height={height}
          style={{ maxWidth: '100%', borderRadius: '4px' }}
          loading="lazy"
          {...props}
        />
      );
    },

    // Links: render wiki-links as styled spans, external links open in new tab
    a: ({ href, children, ...props }) => {
      if (href?.startsWith('obsidian-link://')) {
        return (
          <span className="ob-wikilink" title={decodeURIComponent(href.replace('obsidian-link://', ''))}>
            {children}
          </span>
        );
      }
      return (
        <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
          {children}
        </a>
      );
    },

    // Blockquotes: detect callout markers and render as styled callout boxes
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    blockquote: ({ children, node, ref, ...props }) => {
      const childArray = React.Children.toArray(children);

      for (let i = 0; i < childArray.length; i++) {
        const child = childArray[i];
        if (React.isValidElement(child) && child.props.children) {
          const grandchildren = React.Children.toArray(child.props.children);
          for (const gc of grandchildren) {
            if (typeof gc === 'string') {
              const markerMatch = gc.match(/<!--callout:(\w+):([+-]?):(.*)-->/);
              if (markerMatch) {
                const type = markerMatch[1];
                const foldable = markerMatch[2];
                const title = markerMatch[3] || type.charAt(0).toUpperCase() + type.slice(1);
                const icon = CALLOUT_ICONS[type] || CALLOUT_ICONS['note'];
                const color = CALLOUT_COLORS[type] || CALLOUT_COLORS['note'];

                const filteredChildren = childArray.map((c, idx) => {
                  if (idx === i && React.isValidElement(c)) {
                    const filteredGC = React.Children.toArray(c.props.children).filter(
                      (g) => !(typeof g === 'string' && g.includes('<!--callout:'))
                    );
                    return React.cloneElement(c as React.ReactElement, {}, ...filteredGC);
                  }
                  return c;
                });

                return (
                  <div className={`ob-callout ob-callout-${type}`} style={{ borderLeftColor: color }}>
                    <div className="ob-callout-title" style={{ color }}>
                      <span className="ob-callout-icon">{icon}</span>
                      <span>{title}</span>
                      {foldable && <span className="ob-callout-fold">{foldable === '-' ? '\u25B6' : '\u25BC'}</span>}
                    </div>
                    <div className="ob-callout-body">{filteredChildren}</div>
                  </div>
                );
              }
            }
          }
        }
      }

      return <blockquote {...props}>{children}</blockquote>;
    },

    // Audio elements from embed conversion
    audio: ({ src, ...props }: React.AudioHTMLAttributes<HTMLAudioElement>) => {
      let resolvedSrc = src || '';
      if (resolvedSrc.startsWith('obsidian-vault-audio://')) {
        const ref = resolvedSrc.replace('obsidian-vault-audio://', '');
        resolvedSrc = buildDownloadUrl(ref, currentFileDir);
      }
      return <audio controls src={resolvedSrc} style={{ width: '100%', maxWidth: '500px' }} {...props} />;
    },

    // Video elements from embed conversion
    video: ({ src, ...props }: React.VideoHTMLAttributes<HTMLVideoElement>) => {
      let resolvedSrc = src || '';
      if (resolvedSrc.startsWith('obsidian-vault-video://')) {
        const ref = resolvedSrc.replace('obsidian-vault-video://', '');
        resolvedSrc = buildDownloadUrl(ref, currentFileDir);
      }
      return <video controls src={resolvedSrc} style={{ width: '100%', maxWidth: '100%', borderRadius: '4px' }} {...props} />;
    },
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface ObsidianMarkdownProps {
  /** Raw markdown content (may contain Obsidian syntax). */
  content: string;
  /** Vault-relative path of the file being rendered (e.g. "notes/session-1.md").
   *  Used to resolve relative image/link references. */
  filePath?: string;
  /** Additional CSS class name. */
  className?: string;
}

export const ObsidianMarkdown: React.FC<ObsidianMarkdownProps> = ({
  content,
  filePath = '',
  className = '',
}) => {
  const currentFileDir = useMemo(() => dirOf(filePath), [filePath]);

  const processedContent = useMemo(
    () => preprocessObsidian(content),
    [content]
  );

  const components = useMemo(
    () => createComponents(currentFileDir),
    [currentFileDir]
  );

  return (
    <div className={`ob-markdown ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={components}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  );
};
