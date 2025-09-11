/**
 * Custom transformer for JavaScript files
 * Handles IIFE patterns and jQuery plugins
 */

module.exports = {
  process(sourceText, sourcePath) {
    // Skip transformation for node_modules and minified files
    if (sourcePath.includes('node_modules') || sourcePath.includes('.min.js')) {
      return { code: sourceText };
    }
    
    // Handle IIFE patterns - unwrap them for testing
    let transformed = sourceText;
    
    // Remove IIFE wrapper if present
    const iifePattern = /^\s*\(\s*function\s*\(\s*\)\s*{([\s\S]*?)}\s*\)\s*\(\s*\)\s*;?\s*$/;
    const iifeMatch = sourceText.match(iifePattern);
    if (iifeMatch) {
      transformed = iifeMatch[1];
    }
    
    // Remove jQuery document ready wrapper if present
    const jqueryReadyPattern = /\$\(document\)\.ready\s*\(\s*function\s*\(\s*\)\s*{([\s\S]*?)}\s*\)\s*;?/;
    const jqueryMatch = transformed.match(jqueryReadyPattern);
    if (jqueryMatch) {
      // Keep the initialization code but make it callable
      transformed = transformed.replace(jqueryReadyPattern, 
        `if (typeof window !== 'undefined' && window.IS_TESTING !== true) {
          $(document).ready(function() {${jqueryMatch[1]}});
        }`
      );
    }
    
    // Export any global objects for testing
    const globalObjects = ['NotificationManager', 'FavoritesManager', 'ConferenceStateManager'];
    globalObjects.forEach(obj => {
      if (transformed.includes(`const ${obj} = {`) || transformed.includes(`var ${obj} = {`)) {
        transformed += `\nif (typeof module !== 'undefined' && module.exports) { module.exports.${obj} = ${obj}; }`;
      }
    });
    
    // Ensure 'use strict' is at the top if present
    if (transformed.includes("'use strict'")) {
      transformed = transformed.replace(/['"]use strict['"];?/g, '');
      transformed = "'use strict';\n" + transformed;
    }
    
    return { code: transformed };
  },
};