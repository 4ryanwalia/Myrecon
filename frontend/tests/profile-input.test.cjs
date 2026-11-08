const {test} = require('node:test');
const assert = require('node:assert/strict');
const {parse,shared,autoGate} = require('../assets/js/profile-input.js');
const valid = [ ['@example.name','example.name'], ['example-name','example-name'], ['https://www.instagram.com/example.name/?utm_source=x#bio','example.name'], ['https://www.tiktok.com/@example.name','example.name'], ['https://github.com/example-name','example-name'] ];
for (const [input,handle] of valid) test(input,()=>assert.equal(parse(input).handle,handle));
for (const input of ['https://instagram.com/reel/abc','https://instagram.com/p/abc','https://tiktok.com/@alice/video/123','https://github.com/search?q=alice','https://github.com/login','https://github.com/a/repo','https://instagram.com.evil.test/alice','https://evil.test/alice','https://github.com@evil.test/alice','https://github.com/a/../alice','https://github.com/%61lice','https://github.com//alice','ftp://github.com/alice','https://github.com:8443/alice','https://vm.tiktok.com/abc','@@alice','https://[bad','https://instagram.com/reels']) test('reject '+input,()=>assert.ok(parse(input).error));
test('tracking removed',()=>assert.equal(parse(valid[2][0]).url,'https://www.instagram.com/example.name'));

test('profile links without a scheme use the same validation and canonical URL',()=>{
  for (const input of ['instagram.com/example.name', 'www.instagram.com/example.name/?utm_source=share', 'tiktok.com/@example.name', 'www.tiktok.com/@example.name', 'github.com/example-name', 'WWW.GITHUB.COM/example-name']) {
    assert.deepEqual(parse(input), parse('https://' + input));
    assert.ok(parse(input).url);
  }
  for (const input of ['instagram.com/reel/abc', 'tiktok.com/@alice/video/123', 'github.com/search?q=alice', 'github.com/a/../alice', 'github.com/%61lice', 'github.com//alice', 'github.com.evil.test/alice', 'github.com@evil.test/alice']) {
    assert.ok(parse(input).error, input);
  }
});
test('shared title',()=>assert.equal(shared('A profile\nhttps://github.com/alice').handle,'alice'));
test('ambiguous shares',()=>assert.ok(shared('https://github.com/alice https://instagram.com/bob').error));
test('duplicate auto scans',()=>{ const gate=autoGate(); const p=parse('https://github.com/alice'); assert.equal(gate.accept(p),true); assert.equal(gate.accept(p),false); assert.equal(gate.accept(parse('@alice')),false); gate.reset(); assert.equal(gate.accept(p),true); });
