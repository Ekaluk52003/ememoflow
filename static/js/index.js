import '../css/tailwind.css';
import '../css/base.css';
import Alpine from 'alpinejs';
import './userSearch.js';
import { Editor } from "@tiptap/core";
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
import ImageResize from 'tiptap-extension-resize-image';


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
  Alpine.data("editor", (content = "") => {
    let editor;

    return {
      htmlContent: content,
      updatedAt: Date.now(),
      headingOpen: false,
      colorPickerOpen: false,
      highlightPickerOpen: false,
      currentColor: '#000000',
      currentHighlight: 'transparent',
      isToolbarFixed: false,

      init() {
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
              bold: false, 
            }),
            TextStyle,
            Color.configure({ types: ['textStyle'] }),
           
            ImageResize.configure({
              inline: true,
              allowBase64: true,
            }),
            CustomBold,

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
          const toolbar = this.$refs.toolbar;
          const wrapper = document.createElement('div');
          wrapper.style.position = 'sticky';
          wrapper.style.top = '0';
          wrapper.style.zIndex = '1000';
          wrapper.style.backgroundColor = 'white';
          wrapper.style.width = '100%';

          toolbar.parentNode.insertBefore(wrapper, toolbar);
          wrapper.appendChild(toolbar);

          window.addEventListener('scroll', () => {
            const scrollPosition = window.pageYOffset || document.documentElement.scrollTop;
            const toolbarOffset = wrapper.offsetTop;

            if (scrollPosition > toolbarOffset) {
              if (!this.isToolbarFixed) {
                wrapper.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)';
                this.isToolbarFixed = true;
              }
            } else {
              if (this.isToolbarFixed) {
                wrapper.style.boxShadow = 'none';
                this.isToolbarFixed = false;
              }
            }
          }, { passive: true });
        });
      },

      isLoaded() {
        return editor;
      },
      isActive(type, opts = {}) {
        if (!editor) return false;
        return editor.isActive(type, opts);
      },
      toggleHeading(opts) {
        if (!editor) return;
        editor.chain().focus().toggleHeading(opts).run();
      },

      toggleBold() {
        if (!editor) return;
        const { color } = editor.getAttributes('textStyle');
        editor.chain().focus().toggleBold().run();
        if (editor.isActive('bold')) {
          editor.chain().focus().updateAttributes('bold', { color }).run();
        }

      },

      toggleTextLeft() {
        if (!editor) return;
        editor.chain().focus().setTextAlign('left').run();
      },
      promptForImageUrl() {
        if (!editor) return;
        const url = window.prompt('Enter the image URL:');
        if (url) {
          editor.chain().focus().setImage({ src: url }).run()
        }
      },

      toggleTextCenter() {
        if (!editor) return;
        editor.chain().focus().setTextAlign('center').run();
      },

      toggleTextRight() {
        if (!editor) return;
        editor.chain().focus().setTextAlign('right').run();
      },

      toggleTextJustify() {
        if (!editor) return;
        editor.chain().focus().setTextAlign('justify').run();
      },

      toggleItalic() {
        if (!editor) return;
        editor.chain().toggleItalic().focus().run();
      },
      toggleStrike() {
        if (!editor) return;
        editor.chain().toggleStrike().focus().run();
      },
      toggleRedFont() {
        if (!editor) return;
        editor.chain().setColor("#ff0000").focus().run();
      },
      toggleUnsetFontColor() {
        if (!editor) return;
        editor.chain().unsetColor().focus().run();
      },
      updateCurrentColor() {
        if (!editor) return;
        let color = editor.getAttributes('textStyle').color;
        if (editor.isActive('bold')) {
          color = editor.getAttributes('bold').color || color;
        }
        this.currentColor = color || '#000000';
      },
      updateCurrentHighlight() {
        if (!editor) return;
        this.currentHighlight = editor.getAttributes('highlight').color || 'transparent';
      },

      setTextColor(color) {
        if (!editor) return;
        editor.chain().focus().setColor(color).run();
        if (editor.isActive('bold')) {
          editor.chain().focus().updateAttributes('bold', { color }).run();
        }
        this.colorPickerOpen = false;
        this.updateCurrentColor();
      },
      setHighlightColor(color) {
        if (!editor) return;
        editor.chain().focus().toggleHighlight({ color }).run();
        this.highlightPickerOpen = false;
        this.updateCurrentHighlight();
      },

      isActiveColor(color) {
        if (!editor) return false;
        return this.currentColor === color;
      },
      isActiveHighlight(color) {
        if (!editor) return false;
        return this.currentHighlight === color;
      },
      toggleInsertTable() {
        if (!editor) return;
        editor
          .chain()
          .insertTable({ rows: 2, cols: 2, withHeaderRow: true })
          .focus()
          .run();
      },
      toggleAddColumnBefore() {
        if (!editor) return;
        editor.chain().addColumnBefore().focus().run();
      },
      toggleAddColumnAfter() {
        if (!editor) return;
        editor.chain().addColumnAfter().focus().run();
      },
      toggleDelColumn() {
        if (!editor) return;
        editor.chain().deleteColumn().focus().run();
      },
      toggleAddRowBefore() {
        if (!editor) return;
        editor.chain().addRowBefore().focus().run();
      },
      toggleAddRowAfter() {
        if (!editor) return;
        editor.chain().addRowAfter().focus().run();
      },
      toggleDelRow() {
        if (!editor) return;
        editor.chain().deleteRow().focus().run();
      },
      toggleDelTable() {
        if (!editor) return;
        editor.chain().deleteTable().focus().run();
      },
      toggleUndo() {
        if (!editor) return;
        editor.chain().undo().focus().run();
      },
      toggleRedo() {
        if (!editor) return;
        editor.chain().redo().focus().run();
      },

      toggleParagraph() {
        if (!editor) return;
        editor.chain().setParagraph().focus().run();
      },
      toggleBulletList() {
        if (!editor) return;
        editor.chain().focus().toggleBulletList().run();
      },
      clearFormatting() {
        if (!editor) return;
        editor.chain()
          .focus()
          .unsetAllMarks() 
          .clearNodes() 
          .run();
      },
      indentText() {
        if (!editor) return;
        editor.chain().focus().indent().run();
      },
      outdentText() {
        if (!editor) return;
        editor.chain().focus().outdent().run();
      },

      handleImageUpload() {
        if (!editor) return;

        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';

        input.onchange = () => {
          const file = input.files[0];
          if (!file) return;

          // Validate file type
          if (!file.type.startsWith('image/')) {
            alert('Please upload an image file');
            return;
          }

          // Count existing images
          const content = editor.getJSON();
          let imageCount = 0;
          const countImages = (node) => {
            if (node.type === 'image') imageCount++;
            if (node.content) node.content.forEach(countImages);
          };
          content.content.forEach(countImages);

          if (imageCount >= 2) {
            alert('Maximum 2 images allowed');
            return;
          }

          // Create image preview
          const reader = new FileReader();
          reader.onload = (e) => {
            editor.chain().focus().setImage({ src: e.target.result }).run();
          };
          reader.readAsDataURL(file);
        };

        input.click();
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
      dropdown.open = false;
    }
  });
});
