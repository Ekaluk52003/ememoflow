
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
import { marked } from 'marked';
import DOMPurify from 'dompurify';

window.marked = marked;
window.DOMPurify = DOMPurify;
Alpine.data('app', () => ({
  open: false,
}));

// Tiptap editor on alpine init
document.addEventListener("alpine:init", () => {
  Alpine.data("editor", (content, editable) => {
    let editor; // Alpine's reactive engine automatically wraps component properties in proxy objects. Attempting to use a proxied editor instance to apply a transaction will cause a "Range Error: Applying a mismatched transaction", so be sure to unwrap it using Alpine.raw(), or simply avoid storing your editor as a component property, as shown in this example.

    return {
      updatedAt: Date.now(), // force Alpine to rerender on selection change
      htmlContent:content,


      init() {
        const _this = this;

        editor = new Editor({
          element: this.$refs.element,
          editable:editable || false,
          editorProps: {
            attributes: {
              class: 'rounded-b-lg border-t-4',
            },
          },
          extensions: [
            StarterKit,
            TextStyle,
            Color,
            Image,
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
          ],
          content: content,


          onCreate({ editor }) {
            _this.updatedAt = Date.now();
          },
          onUpdate({ editor }) {
            _this.updatedAt = Date.now();

            _this.htmlContent = editor.getHTML();
          },
          onSelectionUpdate({ editor }) {
            _this.updatedAt = Date.now();
          },
        });

      },
      handleFileUpload(event) {
        const file = event.target.files[0];
        uploadImage(file)
          .then((imageUrl) => {
            editor.chain().focus().setImage({ src: imageUrl }).run();
          })
          .catch((error) => {
            console.error('Error uploading image:', error);
          });
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
        editor.chain().toggleBold().focus().run();
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

      async setContent(html) {

              const details = editor.getText()
              console.log('detail', details)

              editor.commands.clearContent();

              const csrftoken = getCookie('csrftoken');
              const response = await fetch("/documents/prompt/", {
                  method: "POST",
                  headers: {
                    "Content-Type": "application/json",
                    'X-CSRFToken': csrftoken
                },
                body: JSON.stringify({ message:details }) });

                const reader = response.body.getReader();
                let content = '';

                while (true) {
                  const { done, value } = await reader.read();
                  if (done) break;
                  content += new TextDecoder().decode(value);
                  const cleanHtml = '<strong>AI Rewrite:</strong>'+DOMPurify.sanitize(marked(content));
                  editor.commands.setContent(cleanHtml);
                }

                // Directly insert the HTML content

              }

    };
  });
});


// Add Alpine object to the window scope
window.Alpine = Alpine

// initialize Alpine
Alpine.start()

window.htmx = require('htmx.org');