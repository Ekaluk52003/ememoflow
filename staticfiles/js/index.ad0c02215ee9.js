
import '../css/tailwind.css';
import '../css/base.css';
import Alpine from 'alpinejs';
import { Editor } from "@tiptap/core";
import { Image } from "@tiptap/extension-image";
import StarterKit from "@tiptap/starter-kit";
import TextStyle from "@tiptap/extension-text-style";
import { Color } from "@tiptap/extension-color";
import Table from "@tiptap/extension-table";
import TableCell from "@tiptap/extension-table-cell";
import TableHeader from "@tiptap/extension-table-header";
import TableRow from "@tiptap/extension-table-row";
import TextAlign from '@tiptap/extension-text-align'
import Highlight from '@tiptap/extension-highlight'
import { Extension } from '@tiptap/core'
import Bold from '@tiptap/extension-bold';
import { marked } from 'marked';
// import BulletList from '@tiptap/extension-bullet-list'
// import ListItem from '@tiptap/extension-list-item'
// import Paragraph from '@tiptap/extension-paragraph'

// window.marked = marked;

// Alpine.data('app', () => ({
//   open: false,

// }));

const CustomBold = Bold.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      color: {
        default: null,
        parseHTML: element => element.style.color,
        renderHTML: attributes => {
          if (!attributes.color) {
            return {};
          }
          return {
            style: `color: ${attributes.color}`,
          };
        },
      },
    };
  },
});


const CustomIndent = Extension.create({
  name: 'customIndent',

  addGlobalAttributes() {
    return [
      {
        types: ['paragraph', 'heading'],
        attributes: {
          indent: {
            default: 0,
            renderHTML: attributes => ({
              style: `margin-left: ${attributes.indent * 2}em;`
            }),
            parseHTML: element => {
              const indent = parseInt(element.style.marginLeft) / 2
              return isNaN(indent) ? 0 : indent
            }
          }
        }
      }
    ]
  },

  addCommands() {
    return {
      indent: () => ({ tr, state, dispatch }) => {
        const { selection } = state
        tr.setNodeMarkup(selection.$anchor.blockRange().start, null, {
          ...selection.$anchor.parent.attrs,
          indent: (selection.$anchor.parent.attrs.indent || 0) + 1
        })
        dispatch(tr)
        return true
      },
      outdent: () => ({ tr, state, dispatch }) => {
        const { selection } = state
        const currentIndent = selection.$anchor.parent.attrs.indent || 0
        if (currentIndent > 0) {
          tr.setNodeMarkup(selection.$anchor.blockRange().start, null, {
            ...selection.$anchor.parent.attrs,
            indent: currentIndent - 1
          })
          dispatch(tr)
        }
        return true
      }
    }
  }
})


// Tiptap editor on alpine init
document.addEventListener("alpine:init", () => {
  Alpine.data("editor", (initialContent) => {
    let editor; // Alpine's reactive engine automatically wraps component properties in proxy objects. Attempting to use a proxied editor instance to apply a transaction will cause a "Range Error: Applying a mismatched transaction", so be sure to unwrap it using Alpine.raw(), or simply avoid storing your editor as a component property, as shown in this example.

    return {
      updatedAt: Date.now(), // force Alpine to rerender on selection change
      htmlContent:initialContent,
      headingOpen: false,
      colorPickerOpen: false,
      highlightPickerOpen: false,
      currentColor: '#000000',
      currentHighlight: 'transparent',
      isToolbarFixed: false,
      toolbarOffsetTop: 0,
    toolbarInitialWidth: 0,
    lastScrollPosition: 0,

    handleScroll() {
      const toolbar = this.$refs.toolbar;
      const container = this.$refs.editorContainer;
      if (!toolbar || !container) return;

      if (!this.toolbarOffsetTop) {
        this.toolbarOffsetTop = toolbar.offsetTop;
        this.toolbarInitialWidth = toolbar.offsetWidth;
      }

      const scrollPosition = window.pageYOffset || document.documentElement.scrollTop;
      this.lastScrollPosition = scrollPosition;

      if (scrollPosition > this.toolbarOffsetTop && !this.isToolbarFixed) {
        toolbar.style.position = 'fixed';
        toolbar.style.top = '0';
        toolbar.style.left = '0';
        toolbar.style.right = '0';
        toolbar.style.width = '100%';
        toolbar.style.zIndex = '1000';
        container.style.paddingTop = `${toolbar.offsetHeight}px`;
        this.isToolbarFixed = true;
      } else if (scrollPosition <= this.toolbarOffsetTop && this.isToolbarFixed) {
        toolbar.style.position = '';
        toolbar.style.top = '';
        toolbar.style.left = '';
        toolbar.style.right = '';
        toolbar.style.width = `${this.toolbarInitialWidth}px`;
        toolbar.style.zIndex = '';
        container.style.paddingTop = '';
        this.isToolbarFixed = false;
      }
    },
    preventScrollOnFocus(event) {
      // Prevent scrolling when focusing on toolbar elements
      if (this.isToolbarFixed) {
        window.scrollTo(0, this.lastScrollPosition);
      }
    },

      init() {


        if (this.$refs.element) {
          const _this = this;

          editor = new Editor({
            element: this.$refs.element,
            editable:true,
            content: this.htmlContent,
            editorProps: {
              attributes: {
                class: 'rounded-b-lg border-t-4',
              },
            },
            extensions: [
              StarterKit.configure({
                bold: false, // Disable default bold
              }),
              TextStyle,
              Color.configure({ types: ['textStyle'] }),
              Image,
              CustomBold,

              // ImageResize,
              Table.configure({
                HTMLAttributes: {
                  class: "mytable",
                },
                resizable: true,
                allowTableNodeSelection: true,
              }),
              TableRow,
              TableHeader,
              TableCell,
              TextAlign.configure({
                types: ['heading', 'paragraph'],
              }),
              Highlight.configure({
                multicolor: true,
              }),
              CustomIndent,


            ],

            onCreate({ editor }) {
              _this.updatedAt = Date.now();
            },
            onUpdate({ editor }) {
              _this.updatedAt = Date.now();
              _this.htmlContent = editor.getHTML();
              _this.updateCurrentColor();
              _this.updateCurrentHighlight();
            },
            onSelectionUpdate({ editor }) {
              _this.updatedAt = Date.now();
              _this.updateCurrentColor();
              _this.updateCurrentHighlight();
            },
          });
          this.updateCurrentColor();
          this.updateCurrentHighlight();
          this.$nextTick(() => {
            window.addEventListener('scroll', () => this.handleScroll());
            window.addEventListener('resize', () => {
              this.toolbarOffsetTop = 0;
              this.toolbarInitialWidth = 0;
              this.handleScroll();
            });

            // Add event listeners to prevent scrolling on focus
            const toolbarButtons = this.$refs.toolbar.querySelectorAll('button, input, select, textarea');
            toolbarButtons.forEach(button => {
              button.addEventListener('focus', this.preventScrollOnFocus);
            });

            this.handleScroll(); // Initial call to set correct state
          });

            // Clean up event listeners
      this.$cleanup = () => {
        window.removeEventListener('scroll', () => this.handleScroll());
        window.removeEventListener('resize', () => this.handleScroll());
        const toolbarButtons = this.$refs.toolbar.querySelectorAll('button, input, select, textarea');
        toolbarButtons.forEach(button => {
          button.removeEventListener('focus', this.preventScrollOnFocus);
        });
      };
  

        }

      },

      isLoaded() {
        return editor;
      },
      isActive(type, opts = {}) {
        return editor.isActive(type, opts);
      },
      toggleHeading(opts) {
        editor.chain().toggleHeading(opts).focus().run();
      },
      toggleBold() {
        const { color } = editor.getAttributes('textStyle');
        editor.chain().focus().toggleBold().run();
        if (editor.isActive('bold')) {
          editor.chain().focus().updateAttributes('bold', { color }).run();
        }
      },
      toggleTextLeft() {
        editor.chain().focus().setTextAlign('left').run();
      },

      toggleTextCenter() {
        editor.chain().focus().setTextAlign('center').run();
      },

      toggleTextRight() {
        editor.chain().focus().setTextAlign('right').run();
      },

      toggleTextJustify() {
        editor.chain().focus().setTextAlign('justify').run();
      },

      toggleItalic() {
        editor.chain().toggleItalic().focus().run();
      },
      toggleStrike() {
        editor.chain().toggleStrike().focus().run();
      },
      toggleRedFont() {
        editor.chain().setColor("#ff0000").focus().run();
      },
      toggleUnsetFontColor() {
        editor.chain().unsetColor().focus().run();
      },
      updateCurrentColor() {
        let color = editor.getAttributes('textStyle').color;
        if (editor.isActive('bold')) {
          color = editor.getAttributes('bold').color || color;
        }
        this.currentColor = color || '#000000';
      },
      updateCurrentHighlight() {
        this.currentHighlight = editor.getAttributes('highlight').color || 'transparent';
      },

      setTextColor(color) {
        editor.chain().focus().setColor(color).run();
        if (editor.isActive('bold')) {
          editor.chain().focus().updateAttributes('bold', { color }).run();
        }
        this.colorPickerOpen = false;
        this.updateCurrentColor();
      },
      setHighlightColor(color) {
        editor.chain().focus().toggleHighlight({ color }).run();
        this.highlightPickerOpen = false;
        this.updateCurrentHighlight();
      },

      isActiveColor(color) {
        return this.currentColor === color;
      },
      isActiveHighlight(color) {
        return this.currentHighlight === color;
      },
      toggleInsertTable() {
        editor
          .chain()
          .insertTable({ rows: 2, cols: 2, withHeaderRow: true })
          .focus()
          .run();
      },
      toggleAddColumnBefore() {
        editor.chain().addColumnBefore().focus().run();
      },
      toggleAddColumnAfter() {
        editor.chain().addColumnAfter().focus().run();
      },
      toggleDelColumn() {
        editor.chain().deleteColumn().focus().run();
      },
      toggleAddRowBefore() {
        editor.chain().addRowBefore().focus().run();
      },
      toggleAddRowAfter() {
        editor.chain().addRowAfter().focus().run();
      },
      toggleDelRow() {
        editor.chain().deleteRow().focus().run();
      },
      toggleDelTable() {
        editor.chain().deleteTable().focus().run();
      },
      toggleUndo() {
        editor.chain().undo().focus().run();
      },
      toggleRedo() {
        editor.chain().redo().focus().run();
      },

      toggleParagraph() {
      editor.chain().setParagraph().focus().run();
      },
      toggleBulletList() {
        editor.chain().focus().toggleBulletList().run();
      },
      clearFormatting() {
        editor.chain()
          .focus()
          .unsetAllMarks() // Removes inline formatting like bold, italic, etc.
          .clearNodes() // Clears block-level formatting like headings, lists, etc.
          .run();
      },
      indentText() {
        editor.chain().focus().indent().run();
      },
      outdentText() {
        editor.chain().focus().outdent().run();
      },



    };

  });

});


// Add Alpine object to the window scope
window.Alpine = Alpine

// initialize Alpine
Alpine.start()

window.htmx = require('htmx.org');



window.addEventListener('click', function(e) {
  document.querySelectorAll('.dropdown').forEach(function(dropdown) {
    if (!dropdown.contains(e.target)) {
      // Click was outside the dropdown, close it
      dropdown.open = false;
    }
  });
});

