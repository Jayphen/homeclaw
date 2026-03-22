/** @type {Array<{title: string, items: Array<{title: string, href: string}>}>} */
export const nav = [
  {
    title: 'Getting Started',
    items: [
      { title: 'Introduction', href: '/' },
      { title: 'Installation', href: '/getting-started/installation' },
      { title: 'Configuration', href: '/getting-started/configuration' }
    ]
  },
  {
    title: 'Guides',
    items: [
      { title: 'Channels', href: '/guides/channels' },
      { title: 'Memory', href: '/guides/memory' },
      { title: 'Contacts', href: '/guides/contacts' },
      { title: 'Scheduler & Routines', href: '/guides/scheduler' },
      { title: 'Plugins', href: '/guides/plugins' }
    ]
  },
  {
    title: 'Development',
    items: [
      { title: 'Development Guide', href: '/development/guide' },
      { title: 'Architecture', href: '/development/architecture' },
      { title: 'Adding Tools', href: '/development/tools' }
    ]
  }
];
