let n = 0;
export const uid = () => 'id-' + ++n;
export const getUid = uid;
export default uid;
