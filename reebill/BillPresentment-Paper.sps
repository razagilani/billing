<?xml version="1.0" encoding="UTF-8"?>
<structure version="9" htmlmode="strict" relativeto="*SPS" encodinghtml="UTF-8" encodingrtf="ISO-8859-1" encodingpdf="UTF-8" useimportschema="1" embed-images="1">
	<parameters/>
	<schemasources>
		<namespaces>
			<nspair prefix="sb" uri="skylinebill"/>
			<nspair prefix="ub" uri="utilitybill"/>
		</namespaces>
		<schemasources>
			<xsdschemasource name="XML" main="1" schemafile="C:\workspace-skyline\billing\UtilityBill.xsd" workingxmlfile="C:\workspace-skyline\billing\sample\Dominion-101-20090528.xml">
				<xmltablesupport/>
				<textstateicons/>
			</xsdschemasource>
		</schemasources>
	</schemasources>
	<modules>
		<module spsfile="BillPresentment.sps"/>
	</modules>
	<flags>
		<scripts/>
		<globalparts/>
		<designfragments/>
		<pagelayouts/>
	</flags>
	<scripts>
		<script language="javascript"/>
	</scripts>
	<importedxslt/>
	<globalstyles/>
	<mainparts>
		<children>
			<globaltemplate subtype="main" match="/">
				<children>
					<documentsection>
						<properties columncount="1" columngap="0.50in" headerfooterheight="fixed" pagemultiplepages="0" pagenumberingformat="1" pagenumberingstartat="auto" pagestart="next" paperheight="11in" papermarginbottom="0.79in" papermarginfooter="0.30in" papermarginheader="0.30in" papermarginleft="0.60in" papermarginright="0.60in" papermargintop="0.79in" paperwidth="8.50in"/>
					</documentsection>
					<tgrid>
						<properties border="0" width="100%"/>
						<children>
							<tgridbody-cols>
								<children>
									<tgridcol>
										<properties width="50%"/>
									</tgridcol>
									<tgridcol>
										<properties width="50%"/>
									</tgridcol>
								</children>
							</tgridbody-cols>
							<tgridbody-rows>
								<children>
									<tgridrow>
										<children>
											<tgridcell>
												<properties valign="top"/>
												<children>
													<paragraph>
														<children>
															<text fixtext="Account Number">
																<styles font-weight="bold"/>
															</text>
														</children>
													</paragraph>
													<tgrid>
														<properties border="0" width="100%"/>
														<styles font-size="small"/>
														<children>
															<tgridbody-cols>
																<children>
																	<tgridcol>
																		<properties width="5%"/>
																	</tgridcol>
																	<tgridcol>
																		<properties width="95%"/>
																	</tgridcol>
																</children>
															</tgridbody-cols>
															<tgridbody-rows>
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<styles font-size="small"/>
																			</tgridcell>
																			<tgridcell>
																				<styles font-size="small"/>
																				<children>
																					<template subtype="source" match="XML">
																						<children>
																							<template subtype="element" match="ub:utilitybill">
																								<children>
																									<template subtype="attribute" match="account">
																										<children>
																											<content/>
																										</children>
																										<variables/>
																									</template>
																								</children>
																								<variables/>
																							</template>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
															</tgridbody-rows>
														</children>
													</tgrid>
												</children>
											</tgridcell>
											<tgridcell>
												<children>
													<paragraph>
														<children>
															<text fixtext="Mail Payment To">
																<styles font-weight="bold"/>
															</text>
														</children>
													</paragraph>
													<tgrid>
														<properties border="0px" width="100%"/>
														<children>
															<tgridbody-cols>
																<children>
																	<tgridcol>
																		<properties width="5%"/>
																	</tgridcol>
																	<tgridcol/>
																</children>
															</tgridbody-cols>
															<tgridbody-rows>
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell/>
																			<tgridcell>
																				<children>
																					<tgrid>
																						<properties border="0" cellpadding="0" width="100%"/>
																						<children>
																							<tgridbody-cols>
																								<children>
																									<tgridcol/>
																								</children>
																							</tgridbody-cols>
																							<tgridbody-rows>
																								<children>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<children>
																													<text fixtext="Skyline Innovations">
																														<styles font-size="small"/>
																													</text>
																												</children>
																											</tgridcell>
																										</children>
																									</tgridrow>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<children>
																													<text fixtext="2451 18th Street, NW  Second Floor">
																														<styles font-size="small"/>
																													</text>
																												</children>
																											</tgridcell>
																										</children>
																									</tgridrow>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<children>
																													<text fixtext="Washington, DC  2009">
																														<styles font-size="small"/>
																													</text>
																												</children>
																											</tgridcell>
																										</children>
																									</tgridrow>
																								</children>
																							</tgridbody-rows>
																						</children>
																					</tgrid>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
															</tgridbody-rows>
														</children>
													</tgrid>
												</children>
											</tgridcell>
										</children>
									</tgridrow>
								</children>
							</tgridbody-rows>
						</children>
					</tgrid>
					<tgrid>
						<properties border="0" width="100%"/>
						<styles margin-bottom="5px"/>
						<children>
							<tgridbody-cols>
								<children>
									<tgridcol>
										<properties width="50%"/>
									</tgridcol>
									<tgridcol>
										<properties width="50%"/>
									</tgridcol>
								</children>
							</tgridbody-cols>
							<tgridbody-rows>
								<children>
									<tgridrow>
										<children>
											<tgridcell>
												<children>
													<paragraph>
														<children>
															<text fixtext="Billing Address">
																<styles font-weight="bold"/>
															</text>
														</children>
													</paragraph>
													<tgrid>
														<properties border="0" width="100%"/>
														<children>
															<tgridbody-cols>
																<children>
																	<tgridcol>
																		<properties width="5%"/>
																	</tgridcol>
																	<tgridcol>
																		<properties width="95%"/>
																	</tgridcol>
																</children>
															</tgridbody-cols>
															<tgridbody-rows>
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<styles font-size="small"/>
																			</tgridcell>
																			<tgridcell>
																				<styles font-size="small"/>
																				<children>
																					<tgrid>
																						<properties border="0" cellpadding="0"/>
																						<children>
																							<tgridbody-cols>
																								<children>
																									<template subtype="source" match="XML">
																										<children>
																											<template subtype="element" match="ub:utilitybill">
																												<children>
																													<template subtype="element" match="ub:car">
																														<children>
																															<template subtype="element" match="ub:billingaddress">
																																<children>
																																	<tgridcol/>
																																</children>
																																<variables/>
																															</template>
																														</children>
																														<variables/>
																													</template>
																												</children>
																												<variables/>
																											</template>
																										</children>
																										<variables/>
																									</template>
																								</children>
																							</tgridbody-cols>
																							<tgridbody-rows>
																								<children>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<styles font-size="small"/>
																												<children>
																													<template subtype="element" match="ub:addressee">
																														<children>
																															<content/>
																														</children>
																														<variables/>
																													</template>
																												</children>
																											</tgridcell>
																										</children>
																									</tgridrow>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<styles font-size="small"/>
																												<children>
																													<template subtype="element" match="ub:street">
																														<children>
																															<content/>
																														</children>
																														<variables/>
																													</template>
																												</children>
																											</tgridcell>
																										</children>
																									</tgridrow>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<styles font-size="small"/>
																												<children>
																													<template subtype="element" match="ub:city">
																														<children>
																															<content/>
																														</children>
																														<variables/>
																													</template>
																													<text fixtext=", ">
																														<styles font-size="small"/>
																													</text>
																													<template subtype="element" match="ub:state">
																														<children>
																															<content/>
																														</children>
																														<variables/>
																													</template>
																													<text fixtext="  ">
																														<styles font-size="small"/>
																													</text>
																													<template subtype="element" match="ub:postalcode">
																														<children>
																															<content/>
																														</children>
																														<variables/>
																													</template>
																												</children>
																											</tgridcell>
																										</children>
																									</tgridrow>
																								</children>
																							</tgridbody-rows>
																						</children>
																					</tgrid>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
															</tgridbody-rows>
														</children>
													</tgrid>
												</children>
											</tgridcell>
											<tgridcell>
												<children>
													<paragraph>
														<children>
															<text fixtext="Service Location">
																<styles font-weight="bold"/>
															</text>
														</children>
													</paragraph>
													<tgrid>
														<properties border="0" width="100%"/>
														<children>
															<tgridbody-cols>
																<children>
																	<tgridcol>
																		<properties width="5%"/>
																	</tgridcol>
																	<tgridcol>
																		<properties width="95%"/>
																	</tgridcol>
																</children>
															</tgridbody-cols>
															<tgridbody-rows>
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<styles font-size="small"/>
																			</tgridcell>
																			<tgridcell>
																				<styles font-size="small"/>
																				<children>
																					<tgrid>
																						<properties border="0" cellpadding="0"/>
																						<children>
																							<tgridbody-cols>
																								<children>
																									<template subtype="source" match="XML">
																										<children>
																											<template subtype="element" match="ub:utilitybill">
																												<children>
																													<template subtype="element" match="ub:car">
																														<children>
																															<template subtype="element" match="ub:serviceaddress">
																																<children>
																																	<tgridcol/>
																																</children>
																																<variables/>
																															</template>
																														</children>
																														<variables/>
																													</template>
																												</children>
																												<variables/>
																											</template>
																										</children>
																										<variables/>
																									</template>
																								</children>
																							</tgridbody-cols>
																							<tgridbody-rows>
																								<children>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<styles font-size="small"/>
																												<children>
																													<template subtype="element" match="ub:addressee">
																														<children>
																															<content/>
																														</children>
																														<variables/>
																													</template>
																												</children>
																											</tgridcell>
																										</children>
																									</tgridrow>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<styles font-size="small"/>
																												<children>
																													<template subtype="element" match="ub:street">
																														<children>
																															<content/>
																														</children>
																														<variables/>
																													</template>
																												</children>
																											</tgridcell>
																										</children>
																									</tgridrow>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<styles font-size="small"/>
																												<children>
																													<template subtype="element" match="ub:city">
																														<children>
																															<content/>
																														</children>
																														<variables/>
																													</template>
																													<text fixtext="  ">
																														<styles font-size="small"/>
																													</text>
																													<template subtype="element" match="ub:state">
																														<children>
																															<content/>
																														</children>
																														<variables/>
																													</template>
																													<text fixtext="  ">
																														<styles font-size="small"/>
																													</text>
																													<template subtype="element" match="ub:postalcode">
																														<children>
																															<content/>
																														</children>
																														<variables/>
																													</template>
																												</children>
																											</tgridcell>
																										</children>
																									</tgridrow>
																								</children>
																							</tgridbody-rows>
																						</children>
																					</tgrid>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
															</tgridbody-rows>
														</children>
													</tgrid>
												</children>
											</tgridcell>
										</children>
									</tgridrow>
								</children>
							</tgridbody-rows>
						</children>
					</tgrid>
					<tgrid>
						<properties border="0" cellpadding="0px" cellspacing="0px" width="100%"/>
						<children>
							<tgridbody-cols>
								<children>
									<tgridcol>
										<properties width="50%"/>
									</tgridcol>
									<tgridcol>
										<properties width="50%"/>
									</tgridcol>
								</children>
							</tgridbody-cols>
							<tgridbody-rows>
								<children>
									<tgridrow>
										<children>
											<tgridcell>
												<properties valign="top"/>
												<styles border-bottom="2px" border-bottom-color="black" border-bottom-style="solid" padding-bottom="5px"/>
												<children>
													<paragraph>
														<children>
															<text fixtext="Bill Summary">
																<styles font-weight="bold"/>
															</text>
														</children>
													</paragraph>
												</children>
											</tgridcell>
											<tgridcell>
												<styles border-bottom="2px" border-bottom-color="black" border-bottom-style="solid" border-right="2px" border-right-color="black" border-right-style="solid" padding-bottom="5px"/>
												<children>
													<paragraph>
														<children>
															<text fixtext="Due: ">
																<styles font-weight="bold"/>
															</text>
															<template subtype="source" match="XML">
																<children>
																	<template subtype="element" match="ub:utilitybill">
																		<children>
																			<template subtype="element" match="ub:skylinebill">
																				<children>
																					<template subtype="element" match="ub:duedate">
																						<children>
																							<content>
																								<styles font-size="small"/>
																							</content>
																						</children>
																						<variables/>
																					</template>
																				</children>
																				<variables/>
																			</template>
																		</children>
																		<variables/>
																	</template>
																</children>
																<variables/>
															</template>
														</children>
													</paragraph>
												</children>
											</tgridcell>
										</children>
									</tgridrow>
								</children>
							</tgridbody-rows>
						</children>
					</tgrid>
					<tgrid>
						<properties border="0" width="100%"/>
						<children>
							<tgridbody-cols>
								<children>
									<tgridcol>
										<properties valign="top" width="50%"/>
									</tgridcol>
									<tgridcol>
										<properties valign="top" width="50%"/>
									</tgridcol>
								</children>
							</tgridbody-cols>
							<tgridbody-rows>
								<children>
									<tgridrow>
										<children>
											<tgridcell>
												<children>
													<tgrid>
														<properties border="0" width="100%"/>
														<children>
															<tgridbody-cols>
																<children>
																	<tgridcol>
																		<properties width="30%"/>
																	</tgridcol>
																	<tgridcol>
																		<properties valign="top" width="70%"/>
																	</tgridcol>
																</children>
															</tgridbody-cols>
															<tgridbody-rows>
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<styles font-size="small"/>
																				<children>
																					<text fixtext="Bill Issued:">
																						<styles font-weight="bold"/>
																					</text>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<styles font-size="small"/>
																				<children>
																					<template subtype="source" match="XML">
																						<children>
																							<template subtype="element" match="ub:utilitybill">
																								<children>
																									<template subtype="element" match="ub:skylinebill">
																										<children>
																											<template subtype="element" match="ub:issued">
																												<children>
																													<content/>
																												</children>
																												<variables/>
																											</template>
																										</children>
																										<variables/>
																									</template>
																								</children>
																								<variables/>
																							</template>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<styles font-size="small"/>
																				<children>
																					<text fixtext="Bill Period: ">
																						<styles font-weight="bold"/>
																					</text>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<styles font-size="small"/>
																				<children>
																					<template subtype="source" match="XML">
																						<children>
																							<template subtype="element" match="ub:utilitybill">
																								<children>
																									<template subtype="element" match="ub:skylinebill">
																										<children>
																											<template subtype="element" match="ub:billperiodbegin">
																												<children>
																													<content/>
																												</children>
																												<variables/>
																											</template>
																										</children>
																										<variables/>
																									</template>
																								</children>
																								<variables/>
																							</template>
																						</children>
																						<variables/>
																					</template>
																					<text fixtext=" to "/>
																					<template subtype="source" match="XML">
																						<children>
																							<template subtype="element" match="ub:utilitybill">
																								<children>
																									<template subtype="element" match="ub:skylinebill">
																										<children>
																											<template subtype="element" match="ub:billperiodend">
																												<children>
																													<content/>
																												</children>
																												<variables/>
																											</template>
																										</children>
																										<variables/>
																									</template>
																								</children>
																								<variables/>
																							</template>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<styles font-size="small"/>
																			</tgridcell>
																			<tgridcell>
																				<styles font-size="small"/>
																			</tgridcell>
																		</children>
																	</tgridrow>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<styles font-size="small"/>
																			</tgridcell>
																			<tgridcell>
																				<styles font-size="small"/>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
															</tgridbody-rows>
														</children>
													</tgrid>
												</children>
											</tgridcell>
											<tgridcell>
												<children>
													<tgrid>
														<properties border="0" width="100%"/>
														<children>
															<tgridbody-cols>
																<children>
																	<tgridcol>
																		<properties width="40%"/>
																	</tgridcol>
																	<tgridcol>
																		<properties align="right" width="40%"/>
																	</tgridcol>
																	<tgridcol>
																		<properties width="20%"/>
																	</tgridcol>
																</children>
															</tgridbody-cols>
															<tgridbody-rows>
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<styles font-size="small"/>
																				<children>
																					<text fixtext="Utility Charges:">
																						<styles font-weight="bold"/>
																					</text>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<styles font-size="small"/>
																				<children>
																					<text fixtext="$"/>
																					<template subtype="source" match="XML">
																						<children>
																							<template subtype="element" match="ub:utilitybill">
																								<children>
																									<template subtype="element" match="ub:skylinebill">
																										<children>
																											<template subtype="element" match="ub:actualservicecharges">
																												<children>
																													<content/>
																												</children>
																												<variables/>
																											</template>
																										</children>
																										<variables/>
																									</template>
																								</children>
																								<variables/>
																							</template>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<styles font-size="small"/>
																			</tgridcell>
																		</children>
																	</tgridrow>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<styles font-size="small"/>
																				<children>
																					<text fixtext="Bill w/o Skyline: ">
																						<styles font-weight="bold"/>
																					</text>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<styles font-size="small"/>
																				<children>
																					<text fixtext="$"/>
																					<template subtype="source" match="XML">
																						<children>
																							<template subtype="element" match="ub:utilitybill">
																								<children>
																									<template subtype="element" match="ub:skylinebill">
																										<children>
																											<template subtype="element" match="ub:hypotheticalservicecharges">
																												<children>
																													<content/>
																												</children>
																												<variables/>
																											</template>
																										</children>
																										<variables/>
																									</template>
																								</children>
																								<variables/>
																							</template>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<styles font-size="small"/>
																			</tgridcell>
																		</children>
																	</tgridrow>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<styles font-size="small"/>
																				<children>
																					<text fixtext="Skyline Charges:">
																						<styles font-weight="bold"/>
																					</text>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<styles font-size="small"/>
																				<children>
																					<text fixtext="$"/>
																					<template subtype="source" match="XML">
																						<children>
																							<template subtype="element" match="ub:utilitybill">
																								<children>
																									<template subtype="element" match="ub:skylinebill">
																										<children>
																											<template subtype="element" match="ub:skylinecharges">
																												<children>
																													<content/>
																												</children>
																												<variables/>
																											</template>
																										</children>
																										<variables/>
																									</template>
																								</children>
																								<variables/>
																							</template>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<styles font-size="small"/>
																			</tgridcell>
																		</children>
																	</tgridrow>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<styles font-size="small"/>
																				<children>
																					<text fixtext="Your Savings:">
																						<styles font-weight="bold"/>
																					</text>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<styles font-size="small"/>
																				<children>
																					<text fixtext="$"/>
																					<template subtype="source" match="XML">
																						<children>
																							<template subtype="element" match="ub:utilitybill">
																								<children>
																									<template subtype="element" match="ub:skylinebill">
																										<children>
																											<template subtype="element" match="ub:customersavings">
																												<children>
																													<content/>
																												</children>
																												<variables/>
																											</template>
																										</children>
																										<variables/>
																									</template>
																								</children>
																								<variables/>
																							</template>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<styles font-size="small"/>
																			</tgridcell>
																		</children>
																	</tgridrow>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<styles font-size="small"/>
																			</tgridcell>
																			<tgridcell>
																				<styles font-size="small"/>
																			</tgridcell>
																			<tgridcell>
																				<styles font-size="small"/>
																			</tgridcell>
																		</children>
																	</tgridrow>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<styles font-size="small"/>
																				<children>
																					<text fixtext="Total Due:">
																						<styles font-weight="bold"/>
																					</text>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<styles font-size="small"/>
																				<children>
																					<text fixtext="$"/>
																					<template subtype="source" match="XML">
																						<children>
																							<template subtype="element" match="ub:utilitybill">
																								<children>
																									<template subtype="element" match="ub:skylinebill">
																										<children>
																											<template subtype="element" match="ub:skylinecharges">
																												<children>
																													<content/>
																												</children>
																												<variables/>
																											</template>
																										</children>
																										<variables/>
																									</template>
																								</children>
																								<variables/>
																							</template>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<styles font-size="small"/>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
															</tgridbody-rows>
														</children>
													</tgrid>
												</children>
											</tgridcell>
										</children>
									</tgridrow>
								</children>
							</tgridbody-rows>
						</children>
					</tgrid>
					<tgrid>
						<properties border="0" cellpadding="0px" cellspacing="0px" width="100%"/>
						<styles border-collapse="collapse"/>
						<children>
							<tgridbody-cols>
								<children>
									<tgridcol>
										<properties align="right"/>
									</tgridcol>
								</children>
							</tgridbody-cols>
							<tgridbody-rows>
								<children>
									<tgridrow>
										<children>
											<tgridcell>
												<properties align="left"/>
												<children>
													<paragraph>
														<children>
															<text fixtext="Bill Details">
																<styles font-weight="bold"/>
															</text>
														</children>
													</paragraph>
												</children>
											</tgridcell>
										</children>
									</tgridrow>
									<tgridrow>
										<children>
											<tgridcell>
												<properties align="left"/>
												<children>
													<tgrid>
														<properties border="0" width="100%"/>
														<styles border-collapse="collapse"/>
														<children>
															<tgridbody-cols>
																<children>
																	<tgridcol/>
																</children>
															</tgridbody-cols>
															<tgridbody-rows>
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<children>
																					<tgrid>
																						<properties border="0" cellpadding="0px" cellspacing="0px" width="100%"/>
																						<styles font-size="small"/>
																						<children>
																							<tgridbody-cols>
																								<children>
																									<tgridcol>
																										<properties align="left" width="8%"/>
																									</tgridcol>
																									<tgridcol>
																										<properties align="left" width="12%"/>
																									</tgridcol>
																									<tgridcol>
																										<properties align="left" width="12%"/>
																									</tgridcol>
																									<tgridcol>
																										<properties align="left" width="36%"/>
																									</tgridcol>
																									<tgridcol>
																										<properties width="8%"/>
																									</tgridcol>
																									<tgridcol>
																										<properties width="4%"/>
																									</tgridcol>
																									<tgridcol>
																										<properties width="10%"/>
																									</tgridcol>
																									<tgridcol>
																										<properties width="4%"/>
																									</tgridcol>
																									<tgridcol>
																										<properties width="8%"/>
																									</tgridcol>
																									<tgridcol/>
																								</children>
																							</tgridbody-cols>
																							<tgridbody-rows>
																								<children>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																												<children>
																													<text fixtext="Service">
																														<styles font-weight="bold"/>
																													</text>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																												<children>
																													<text fixtext="Rate">
																														<styles font-weight="bold"/>
																													</text>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																											</tgridcell>
																											<tgridcell>
																												<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																												<children>
																													<text fixtext="Description">
																														<styles font-weight="bold"/>
																													</text>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																												<children>
																													<text fixtext="Quantity">
																														<styles font-weight="bold"/>
																													</text>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																											</tgridcell>
																											<tgridcell>
																												<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																												<children>
																													<text fixtext="Rate">
																														<styles font-weight="bold"/>
																													</text>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																											</tgridcell>
																											<tgridcell>
																												<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																												<children>
																													<text fixtext="Amount">
																														<styles font-weight="bold"/>
																													</text>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid" border-right-color="black" border-right-style="solid" border-right-width="1px"/>
																											</tgridcell>
																										</children>
																									</tgridrow>
																								</children>
																							</tgridbody-rows>
																						</children>
																					</tgrid>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<children>
																					<tgrid>
																						<properties border="0" width="100%"/>
																						<styles border-collapse="collapse" font-size="x-small"/>
																						<children>
																							<tgridbody-cols>
																								<children>
																									<tgridcol>
																										<properties align="left" width="8%"/>
																									</tgridcol>
																									<tgridcol>
																										<properties align="left" width="12%"/>
																									</tgridcol>
																									<tgridcol>
																										<properties align="right" width="80%"/>
																									</tgridcol>
																								</children>
																							</tgridbody-cols>
																							<tgridbody-rows>
																								<children>
																									<template subtype="element" match="ub:utilitybill">
																										<children>
																											<template subtype="element" match="ub:details">
																												<children>
																													<tgridrow>
																														<properties valign="top"/>
																														<children>
																															<tgridcell>
																																<children>
																																	<template subtype="attribute" match="service">
																																		<children>
																																			<content/>
																																		</children>
																																		<variables/>
																																	</template>
																																</children>
																															</tgridcell>
																															<tgridcell>
																																<children>
																																	<template subtype="element" match="ub:rateschedule">
																																		<children>
																																			<content/>
																																		</children>
																																		<variables/>
																																	</template>
																																</children>
																															</tgridcell>
																															<tgridcell>
																																<children>
																																	<tgrid>
																																		<properties border="0" width="100%"/>
																																		<styles border-collapse="collapse"/>
																																		<children>
																																			<tgridbody-cols>
																																				<children>
																																					<tgridcol/>
																																				</children>
																																			</tgridbody-cols>
																																			<tgridbody-rows>
																																				<children>
																																					<tgridrow>
																																						<children>
																																							<tgridcell>
																																								<properties align="right"/>
																																								<styles font-size="x-small"/>
																																								<children>
																																									<tgrid>
																																										<properties border="0" width="100%"/>
																																										<styles border-collapse="collapse"/>
																																										<children>
																																											<tgridbody-cols>
																																												<children>
																																													<tgridcol>
																																														<properties align="left" valign="top" width="15%"/>
																																													</tgridcol>
																																													<tgridcol>
																																														<properties align="right" width="85%"/>
																																													</tgridcol>
																																												</children>
																																											</tgridbody-cols>
																																											<tgridbody-rows>
																																												<children>
																																													<template subtype="element" match="ub:chargegroup">
																																														<children>
																																															<tgridrow>
																																																<children>
																																																	<tgridcell/>
																																																	<tgridcell>
																																																		<children>
																																																			<tgrid>
																																																				<properties border="0" width="100%"/>
																																																				<styles border-collapse="collapse"/>
																																																				<children>
																																																					<tgridbody-cols>
																																																						<children>
																																																							<tgridcol/>
																																																						</children>
																																																					</tgridbody-cols>
																																																					<tgridbody-rows>
																																																						<children>
																																																							<tgridrow>
																																																								<children>
																																																									<tgridcell>
																																																										<children>
																																																											<tgrid>
																																																												<properties border="0" width="100%"/>
																																																												<styles border-collapse="collapse"/>
																																																												<children>
																																																													<tgridbody-cols>
																																																														<children>
																																																															<tgridcol>
																																																																<properties align="left" width="48%"/>
																																																															</tgridcol>
																																																															<tgridcol>
																																																																<properties align="right" width="12%"/>
																																																															</tgridcol>
																																																															<tgridcol>
																																																																<properties align="left" width="8%"/>
																																																															</tgridcol>
																																																															<tgridcol>
																																																																<properties align="right" width="12%"/>
																																																															</tgridcol>
																																																															<tgridcol>
																																																																<properties align="left" width="8%"/>
																																																															</tgridcol>
																																																															<tgridcol>
																																																																<properties align="right" width="12%"/>
																																																															</tgridcol>
																																																														</children>
																																																													</tgridbody-cols>
																																																													<tgridbody-rows>
																																																														<children>
																																																															<template subtype="element" filter="@type = &apos;hypothetical&apos;" match="ub:charges">
																																																																<children>
																																																																	<template subtype="element" match="ub:charge">
																																																																		<children>
																																																																			<tgridrow>
																																																																				<children>
																																																																					<tgridcell>
																																																																						<children>
																																																																							<template subtype="element" match="ub:description">
																																																																								<children>
																																																																									<content/>
																																																																								</children>
																																																																								<variables/>
																																																																							</template>
																																																																						</children>
																																																																					</tgridcell>
																																																																					<tgridcell>
																																																																						<children>
																																																																							<template subtype="element" match="ub:quantity">
																																																																								<children>
																																																																									<content/>
																																																																								</children>
																																																																								<variables/>
																																																																							</template>
																																																																						</children>
																																																																					</tgridcell>
																																																																					<tgridcell>
																																																																						<children>
																																																																							<template subtype="element" match="ub:quantity">
																																																																								<children>
																																																																									<template subtype="attribute" match="units">
																																																																										<children>
																																																																											<content/>
																																																																										</children>
																																																																										<variables/>
																																																																									</template>
																																																																								</children>
																																																																								<variables/>
																																																																							</template>
																																																																						</children>
																																																																					</tgridcell>
																																																																					<tgridcell>
																																																																						<children>
																																																																							<text fixtext=" "/>
																																																																							<template subtype="element" match="ub:rate">
																																																																								<children>
																																																																									<content/>
																																																																								</children>
																																																																								<variables/>
																																																																							</template>
																																																																						</children>
																																																																					</tgridcell>
																																																																					<tgridcell>
																																																																						<children>
																																																																							<template subtype="element" match="ub:rate">
																																																																								<children>
																																																																									<template subtype="attribute" match="units">
																																																																										<children>
																																																																											<content/>
																																																																										</children>
																																																																										<variables/>
																																																																									</template>
																																																																								</children>
																																																																								<variables/>
																																																																							</template>
																																																																						</children>
																																																																					</tgridcell>
																																																																					<tgridcell>
																																																																						<properties align="right"/>
																																																																						<children>
																																																																							<template subtype="element" match="ub:total">
																																																																								<children>
																																																																									<content>
																																																																										<format datatype="decimal"/>
																																																																									</content>
																																																																								</children>
																																																																								<variables/>
																																																																							</template>
																																																																						</children>
																																																																					</tgridcell>
																																																																				</children>
																																																																			</tgridrow>
																																																																		</children>
																																																																		<variables/>
																																																																	</template>
																																																																</children>
																																																																<variables/>
																																																															</template>
																																																														</children>
																																																													</tgridbody-rows>
																																																												</children>
																																																											</tgrid>
																																																										</children>
																																																									</tgridcell>
																																																								</children>
																																																							</tgridrow>
																																																						</children>
																																																					</tgridbody-rows>
																																																				</children>
																																																			</tgrid>
																																																		</children>
																																																	</tgridcell>
																																																</children>
																																															</tgridrow>
																																														</children>
																																														<variables/>
																																													</template>
																																												</children>
																																											</tgridbody-rows>
																																										</children>
																																									</tgrid>
																																									<text fixtext="$">
																																										<styles font-size="x-small"/>
																																									</text>
																																									<template subtype="element" filter="@type=&apos;hypothetical&apos;" match="ub:total">
																																										<children>
																																											<content/>
																																										</children>
																																										<variables/>
																																									</template>
																																								</children>
																																							</tgridcell>
																																						</children>
																																					</tgridrow>
																																				</children>
																																			</tgridbody-rows>
																																		</children>
																																	</tgrid>
																																</children>
																															</tgridcell>
																														</children>
																													</tgridrow>
																												</children>
																												<variables/>
																											</template>
																										</children>
																										<variables/>
																									</template>
																								</children>
																							</tgridbody-rows>
																							<tgridfooter-rows>
																								<children>
																									<tgridrow>
																										<children>
																											<tgridcell/>
																											<tgridcell/>
																											<tgridcell>
																												<children>
																													<text fixtext="Total $"/>
																													<autocalc xpath="sum(ub:utilitybill/ub:details/ub:total[@type=&apos;hypothetical&apos;])"/>
																												</children>
																											</tgridcell>
																										</children>
																									</tgridrow>
																								</children>
																							</tgridfooter-rows>
																						</children>
																					</tgrid>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
															</tgridbody-rows>
														</children>
													</tgrid>
												</children>
											</tgridcell>
										</children>
									</tgridrow>
								</children>
							</tgridbody-rows>
						</children>
					</tgrid>
					<tgrid>
						<properties border="0px" width="100%"/>
						<children>
							<tgridbody-cols>
								<children>
									<tgridcol/>
								</children>
							</tgridbody-cols>
							<tgridbody-rows>
								<children>
									<tgridrow>
										<children>
											<tgridcell>
												<children>
													<paragraph>
														<children>
															<text fixtext="Measured Usage">
																<styles font-weight="bold"/>
															</text>
														</children>
													</paragraph>
												</children>
											</tgridcell>
										</children>
									</tgridrow>
									<tgridrow>
										<children>
											<tgridcell>
												<children>
													<tgrid>
														<properties border="0px" cellpadding="0px" cellspacing="0px" width="100%"/>
														<children>
															<tgridbody-cols>
																<children>
																	<tgridcol/>
																</children>
															</tgridbody-cols>
															<tgridheader-rows>
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<children>
																					<tgrid>
																						<properties border="0px" cellpadding="0px" cellspacing="0px" width="100%"/>
																						<styles font-size="small"/>
																						<children>
																							<tgridbody-cols>
																								<children>
																									<tgridcol>
																										<properties width="25%"/>
																									</tgridcol>
																									<tgridcol>
																										<properties width="50%"/>
																									</tgridcol>
																									<tgridcol>
																										<properties width="25%"/>
																									</tgridcol>
																								</children>
																							</tgridbody-cols>
																							<tgridbody-rows>
																								<children>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<properties align="left"/>
																												<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																												<children>
																													<text fixtext="Meter Register"/>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<properties align="left"/>
																												<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid"/>
																												<children>
																													<text fixtext="Description"/>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<properties align="left"/>
																												<styles border-bottom="1px" border-bottom-color="black" border-bottom-style="solid" border-right="1px" border-right-color="black" border-right-style="solid"/>
																												<children>
																													<text fixtext="Total"/>
																												</children>
																											</tgridcell>
																										</children>
																									</tgridrow>
																								</children>
																							</tgridbody-rows>
																						</children>
																					</tgrid>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
															</tgridheader-rows>
															<tgridbody-rows>
																<children>
																	<template subtype="element" match="ub:utilitybill">
																		<children>
																			<template subtype="element" match="ub:measuredusage">
																				<children>
																					<template subtype="element" match="ub:meter">
																						<children>
																							<tgridrow>
																								<children>
																									<tgridcell>
																										<children>
																											<tgrid>
																												<properties border="0px" cellpadding="0px" cellspacing="0px" width="100%"/>
																												<styles font-size="x-small"/>
																												<children>
																													<tgridbody-cols>
																														<children>
																															<tgridcol>
																																<properties width="25%"/>
																															</tgridcol>
																															<tgridcol>
																																<properties width="50%"/>
																															</tgridcol>
																															<tgridcol>
																																<properties width="25%"/>
																															</tgridcol>
																														</children>
																													</tgridbody-cols>
																													<tgridbody-rows>
																														<children>
																															<template subtype="element" filter="@shadow =  true()" match="ub:register">
																																<children>
																																	<tgridrow>
																																		<children>
																																			<tgridcell>
																																				<children>
																																					<template subtype="element" match="ub:identifier">
																																						<children>
																																							<content/>
																																						</children>
																																						<variables/>
																																					</template>
																																				</children>
																																			</tgridcell>
																																			<tgridcell>
																																				<children>
																																					<template subtype="element" match="ub:description">
																																						<children>
																																							<content/>
																																						</children>
																																						<variables/>
																																					</template>
																																				</children>
																																			</tgridcell>
																																			<tgridcell>
																																				<children>
																																					<template subtype="element" match="ub:total">
																																						<children>
																																							<content>
																																								<format datatype="decimal"/>
																																							</content>
																																						</children>
																																						<variables/>
																																					</template>
																																					<text fixtext=" "/>
																																					<template subtype="element" match="ub:units">
																																						<children>
																																							<content/>
																																						</children>
																																						<variables/>
																																					</template>
																																				</children>
																																			</tgridcell>
																																		</children>
																																	</tgridrow>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridbody-rows>
																												</children>
																											</tgrid>
																										</children>
																									</tgridcell>
																								</children>
																							</tgridrow>
																						</children>
																						<variables/>
																					</template>
																				</children>
																				<variables/>
																			</template>
																		</children>
																		<variables/>
																	</template>
																</children>
															</tgridbody-rows>
														</children>
													</tgrid>
												</children>
											</tgridcell>
										</children>
									</tgridrow>
								</children>
							</tgridbody-rows>
						</children>
					</tgrid>
					<newline/>
					<newline/>
				</children>
			</globaltemplate>
		</children>
	</mainparts>
	<globalparts/>
	<pagelayout>
		<properties paperheight="11.69in" paperwidth="8.27in"/>
	</pagelayout>
	<designfragments/>
</structure>
