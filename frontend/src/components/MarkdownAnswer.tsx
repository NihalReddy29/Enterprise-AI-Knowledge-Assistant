import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

export function MarkdownAnswer({ content }: { content: string }) {
    return (
        <div className="text-sm leading-relaxed [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                    p: ({ children }) => <p className="mb-2 whitespace-pre-wrap">{children}</p>,
                    h1: ({ children }) => <h1 className="mb-2 mt-3 text-base font-semibold">{children}</h1>,
                    h2: ({ children }) => <h2 className="mb-2 mt-3 text-sm font-semibold">{children}</h2>,
                    h3: ({ children }) => <h3 className="mb-1 mt-2 text-sm font-semibold">{children}</h3>,
                    ul: ({ children }) => <ul className="mb-2 ml-4 list-disc space-y-1">{children}</ul>,
                    ol: ({ children }) => <ol className="mb-2 ml-4 list-decimal space-y-1">{children}</ol>,
                    li: ({ children }) => <li className="pl-1">{children}</li>,
                    strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                    table: ({ children }) => (
                        <div className="mb-2 overflow-x-auto">
                            <table className="w-full border-collapse text-xs">{children}</table>
                        </div>
                    ),
                    th: ({ children }) => (
                        <th className="border border-line bg-panel-muted px-2 py-1 text-left font-semibold">
                            {children}
                        </th>
                    ),
                    td: ({ children }) => <td className="border border-line px-2 py-1">{children}</td>,
                    code({ className, children, ...props }) {
                        const match = /language-(\w+)/.exec(className || '')
                        const isInline = !match && !String(children).includes('\n')
                        if (isInline) {
                            return (
                                <code className="rounded bg-panel-muted px-1 py-0.5 text-xs text-accent" {...props}>
                                    {children}
                                </code>
                            )
                        }
                        return (
                            <SyntaxHighlighter
                                style={oneDark}
                                language={match?.[1] || 'text'}
                                PreTag="div"
                                customStyle={{ borderRadius: '0.5rem', fontSize: '0.75rem', margin: '0.5rem 0' }}
                            >
                                {String(children).replace(/\n$/, '')}
                            </SyntaxHighlighter>
                        )
                    },
                }}
            >
                {content}
            </ReactMarkdown>
        </div>
    )
}