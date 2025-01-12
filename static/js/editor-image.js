// Image handling extension for the editor
export function setupImageHandling(editor) {
  return {
    handleImageUpload() {
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

        if (imageCount >= 3) {
          alert('Maximum 3 images allowed');
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
    }
  };
}
