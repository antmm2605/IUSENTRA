import test from 'node:test';
import assert from 'node:assert/strict';
import {shapePath} from '../../web/static/vendor/pdfcraft-direct/editor/shape-path.mjs';

test('closed shapes keep the same bounds in every drag direction',()=>{
  for(const kind of ['rectangle','ellipse','triangle','diamond']){
    assert.deepEqual(shapePath(kind,10,20,110,70),shapePath(kind,110,70,10,20));
    assert.equal(shapePath(kind,10,20,110,70).at(-1)[0],'Z');
  }
});
test('arrowheads follow the endpoint and both ends of a double arrow',()=>{
  assert.equal(shapePath('line',10,20,110,70).length,2);
  assert.equal(shapePath('arrow',10,20,110,70).length,5);
  const double=shapePath('double-arrow',10,20,110,70);
  assert.deepEqual(double[3],['L',110,70]);
  assert.deepEqual(double[6],['L',10,20]);
});
test('small gestures create no object and invalid input fails explicitly',()=>{
  assert.deepEqual(shapePath('ellipse',10,10,11,11),[]);
  assert.throws(()=>shapePath('ellipse',NaN,0,100,100));
  assert.throws(()=>shapePath('unknown',0,0,100,100));
});
test('a circle has equal diameters even after a rectangular gesture',()=>{
  assert.deepEqual(shapePath('circle',10,20,110,70),shapePath('ellipse',10,20,60,70));
  assert.deepEqual(shapePath('circle',110,70,10,20),shapePath('ellipse',110,70,60,20));
});
