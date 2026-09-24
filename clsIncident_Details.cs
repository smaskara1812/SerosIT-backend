using System;
using System.Data;
using System.Configuration;
using System.Web;
using System.Web.Security;
using System.Web.UI;
using System.Web.UI.WebControls;
using System.Web.UI.WebControls.WebParts;
using System.Web.UI.HtmlControls;
using System.Data.SqlClient;
using EBS.Classes;
using EBS_Common.Classes;
using System.Text;

namespace EBS.Classes
{
    /// <summary>
    /// Summary description for clsIncident_Details
    /// </summary>
    public class clsIncident_Details: EBS_Common.Classes.clsCommonTableFields // inheriting common fields
    {
        #region Defining Local Variables - Class Level
        private SqlConnection Conn;
        private string strConnString = "";
        #endregion

        # region Defining Property Variables
        private int _Incident_Id;        
        private Int16? _Rig_Id;
        private String _Unit_Name;
        private String _Rig_Incident_No;
        private String _Incident_Date;
        private String _Incident_Time;
        private Int16? _Country_Id;
        private String _Well_No;
       // private Int32 _Incident_No;
        private string _Drilling_Superintendent;
        private string _Safety_Officer;
        private String _Incident_Descr;
        private byte  _Work_Location_Id;
        private byte? _Contact_Expo_Type_Id;
        private byte? _Rig_Operation_Id;
        private string _Incident_Severity;
        private string _Incident_Severity_Potential;
        private byte _Incident_Type_Id;
        private byte _Immediate_Incident_Cause_Id_1;//1
        private byte? _Immediate_Incident_Cause_Id_2;//2
        private String _Immediate_Cause_Descr;
        private String _Corrective_Action;
        private String _Preventive_Action;
        private string _Incident_Status;
        private decimal? _NPT_Hrs_Loss;
        private decimal? _Manhours_Loss;
        private byte? _Financial_Loss_Currency_Id;
        private int? _Financial_Loss_Amt;
        private decimal? _Exchange_Rate;
        private int? _Financial_Loss_BC_Amt;
        private string _Third_Party;
        private string _Incident_Party;
        private Int16? _Contractor_Id;
        private Int16? _Operator_Id;
        private String _Incident_Reported_Dt;
        private String _Incident_Reported_Time;
        private String _Person_Injured;
        private int? _Fs_Emp_Id;
        private String _Emp_Name;
        private byte? _Rank_Id;
        private Int16? _Total_Rig_Exp_Months;
        private string _Comments;
        //private string _Part_Of_Body_Injured;

        private string _Reported_By;
        private byte? _Rptd_By_Rank_Id;
        private int _Wkg_Vessel_Incident_Dtl_Id;
        private string _isImg_Uploaded_Count;


        private byte? _Part_Of_Body_Id_1;
        private byte? _Part_Of_Body_Id_2;
        private byte? _Part_Of_Body_Id_3;
        private byte? _Part_Of_Body_Id_4;
        private string _DMS_Path_QHSE;
        private string _Deleted_Remarks;

        #endregion

        #region Constructor

        public clsIncident_Details(string constr) 
        {
            strConnString = constr;
            Conn = new SqlConnection(strConnString);
        }

        #endregion

        # region Property Declarations

        public int Incident_Id
        {
            get
            {
                return _Incident_Id;
            }
            set
            {
                _Incident_Id = value;
            }
        }

      
        public Int16? Rig_Id
        {
            get
            {
                return _Rig_Id;
            }
            set
            {
                _Rig_Id = value;
            }
        }
        public string Unit_Name
        {
            get
            {
                return _Unit_Name ;
            }
            set
            {
                _Unit_Name = value;
            }
        }


        public byte? Part_Of_Body_Id_1
        {
            get
            {
                return _Part_Of_Body_Id_1;
            }
            set
            {
                _Part_Of_Body_Id_1 = value;
            }
        }
        public byte? Part_Of_Body_Id_2
        {
            get
            {
                return _Part_Of_Body_Id_2;
            }
            set
            {
                _Part_Of_Body_Id_2 = value;
            }
        }
        public byte? Part_Of_Body_Id_3
        {
            get
            {
                return _Part_Of_Body_Id_3;
            }
            set
            {
                _Part_Of_Body_Id_3 = value;
            }
        }
        public byte? Part_Of_Body_Id_4
        {
            get
            {
                return _Part_Of_Body_Id_4;
            }
            set
            {
                _Part_Of_Body_Id_4 = value;
            }
        }

        public string Rig_Incident_No
        {
            get
            {
                return _Rig_Incident_No;
            }
            set
            {
                _Rig_Incident_No = value;
            }
        }
        public string Incident_Date
        {
            get
            {
                return _Incident_Date;
            }
            set
            {
                _Incident_Date = value;
            }
        }

        public string Incident_Time
        {
            get
            {
                return _Incident_Time;
            }
            set
            {
                _Incident_Time = value;
            }
        }
        public Int16?  Country_Id
        {
            get
            {
                return _Country_Id;
            }
            set
            {
                _Country_Id = value;
            }
        }
        public string Well_No
        {
            get
            {
                return _Well_No;
            }
            set
            {
                _Well_No = value;
            }
        }
        
        //public Int32 Incident_No
        //{
        //    get
        //    {
        //        return _Incident_No;
        //    }
        //    set
        //    {
        //        _Incident_No = value;
        //    }
        //}

        public string Drilling_Superintendent
        {
            get
            {
                return _Drilling_Superintendent;
            }
            set
            {
                _Drilling_Superintendent = value;
            }
        }

        public string Safety_Officer
        {
            get
            {
                return _Safety_Officer;
            }
            set
            {
                _Safety_Officer = value;
            }
        }

        public String Incident_Descr
        {
            get
            {
                return _Incident_Descr;
            }
            set
            {
                _Incident_Descr = value;
            }
        }

        public string Incident_Severity
        {
            get
            {
                return _Incident_Severity;
            }
            set
            {
                _Incident_Severity = value;
            }
        }

        public string Incident_Severity_Potential
        {
            get
            {
                return _Incident_Severity_Potential;
            }
            set
            {
                _Incident_Severity_Potential = value;
            }
        }
        
        public byte Incident_Type_Id
        {
            get
            {
                return _Incident_Type_Id;
            }
            set
            {
                _Incident_Type_Id = value;
            }
        }

        public string Incident_Status
        {
            get
            {
                return _Incident_Status;
            }
            set
            {
                _Incident_Status = value;
            }
        }

        public int? Financial_Loss_BC_Amt
        {
            get
            {
                return _Financial_Loss_BC_Amt;
            }
            set
            {
                _Financial_Loss_BC_Amt = value;
            }
        }

        public decimal? Exchange_Rate
        {
            get
            {
                return _Exchange_Rate;
            }
            set
            {
                _Exchange_Rate = value;
            }
        }

        public int? Financial_Loss_Amt
        {
            get
            {
                return _Financial_Loss_Amt;
            }
            set
            {
                _Financial_Loss_Amt = value;
            }
        }

        public byte? Financial_Loss_Currency_Id
        {
            get
            {
                return _Financial_Loss_Currency_Id;
            }
            set
            {
                _Financial_Loss_Currency_Id = value;
            }
        }

        public Decimal? NPT_Hrs_Loss
        {
            get
            {
                return _NPT_Hrs_Loss;
            }
            set
            {
                _NPT_Hrs_Loss = value;
            }
        }

        public Decimal? Manhours_Loss
        {
            get
            {
                return _Manhours_Loss;
            }
            set
            {
                _Manhours_Loss = value;
            }
        }

        public string Preventive_Action
        {
            get
            {
                return _Preventive_Action;
            }
            set
            {
                _Preventive_Action = value;
            }
        }

        public string Corrective_Action
        {
            get
            {
                return _Corrective_Action;
            }
            set
            {
                _Corrective_Action = value;
            }
        }
        public string Immediate_Cause_Descr
        {
            get
            {
                return _Immediate_Cause_Descr;
            }
            set
            {
                _Immediate_Cause_Descr = value;
            }
        }
        public byte  Work_Location_Id
        {
            get
            {
                return _Work_Location_Id;
            }
            set
            {
                _Work_Location_Id = value;
            }
        }
        public byte? Rig_Operation_Id
        {
            get
            {
                return _Rig_Operation_Id;
            }
            set
            {
                _Rig_Operation_Id = value;
            }
        }
        public byte? Contact_Expo_Type_Id
        {
            get
            {
                return _Contact_Expo_Type_Id;
            }
            set
            {
                _Contact_Expo_Type_Id = value;
            }
        }
         
      
        public byte Immediate_Incident_Cause_Id_1
        {
            get
            {
                return _Immediate_Incident_Cause_Id_1;
            }
            set
            {
                _Immediate_Incident_Cause_Id_1 = value;
            }
        }
        
        public byte? Immediate_Incident_Cause_Id_2
        {
            get
            {
                return  _Immediate_Incident_Cause_Id_2;
            }
            set
            {
                 _Immediate_Incident_Cause_Id_2 = value;
            }
        }

        public string Third_Party
        {
            get
            {
                return _Third_Party;
            }
            set
            {
                _Third_Party = value;
            }
        }

        public string Incident_Party
        {
            get
            {
                return _Incident_Party;
            }
            set
            {
                _Incident_Party = value;
            }
        }
        public  Int16? Contractor_Id
        {
            get
            {
                return _Contractor_Id;
            }
            set
            {
                _Contractor_Id = value;
            }
        }

        public  Int16? Operator_Id
        {
            get
            {
                return _Operator_Id;
            }
            set
            {
                _Operator_Id = value;
            }
        }

        public string Incident_Reported_Dt
        {
            get
            {
                return _Incident_Reported_Dt;
            }
            set
            {
                _Incident_Reported_Dt = value;
            }
        }
        public string Incident_Reported_Time
        {
            get
            {
                return _Incident_Reported_Time;
            }
            set
            {
                _Incident_Reported_Time = value;
            }
        }

        public string Person_Injured
        {
            get
            {
                return _Person_Injured;
            }
            set
            {
                _Person_Injured = value;
            }
        }

        public int? Fs_Emp_Id
        {
            get
            {
                return _Fs_Emp_Id;
            }
            set
            {
                _Fs_Emp_Id = value;
            }
        }

        public  string Emp_Name 
        {
            get
            {
                return _Emp_Name ;
            }
            set
            {
                _Emp_Name = value;
            }
        }

        public byte? Rank_Id
        {
            get
            {
                return _Rank_Id;
            }
            set
            {
                _Rank_Id = value;
            }
        }

        public Int16? Total_Rig_Exp_Months 
        {
            get
            {
                return _Total_Rig_Exp_Months;
            }
            set
            {
                _Total_Rig_Exp_Months = value;
            }
        }

        public string Reported_By
        {
            get
            {
                return _Reported_By;
            }
            set
            {
                _Reported_By = value;
            }
        }
        public byte? Rptd_By_Rank_Id
        {
            get
            {
                return _Rptd_By_Rank_Id; 
            }
            set
            {
                _Rptd_By_Rank_Id  = value;
            }
        }
        public string Comments
        {
            get
            {
                return _Comments;
            }
            set
            {
                _Comments = value;
            }
        }

        public int Wkg_Vessel_Incident_Dtl_Id
        {
            get
            {
                return _Wkg_Vessel_Incident_Dtl_Id;
            }
            set
            {
                _Wkg_Vessel_Incident_Dtl_Id = value;
            }
        }
        public string isImg_Uploaded_Count
        {
            get
            {
                return _isImg_Uploaded_Count;
            }
            set
            {
                _isImg_Uploaded_Count = value;
            }
        }

        public string DMS_Path_QHSE
        {
            get
            {
                return _DMS_Path_QHSE;
            }
            set
            {
                _DMS_Path_QHSE = value;
            }
        }
        public string Deleted_Remarks
        {
            get
            {
                return _Deleted_Remarks;
            }
            set
            {
                _Deleted_Remarks = value;
            }
        }
        
        #endregion

        public void InsertMe(ref GridView grdInc_Images, ref SqlTransaction trDML, ref SqlConnection Conn)
        {          


            //SqlTransaction trDML;
            SqlCommand CmdDML;
            
            //Conn.Open();
            //trDML = Conn.BeginTransaction();
            try
            {
                CmdDML = new SqlCommand(OI.Def + "Prc_Incident_Details", Conn, trDML);
                CmdDML.CommandType = CommandType.StoredProcedure;


                CmdDML.Parameters.Add(new SqlParameter("Incident_Id", SqlDbType.Int));
                CmdDML.Parameters["Incident_Id"].Direction = ParameterDirection.Output;  //Required afterward in file saving & Fs Interview Dtl storing logic.
 

                // Changes By Vipin Add Part_Of_Body_Injured
                //CmdDML.Parameters.Add("Part_Of_Body_Injured", System.Data.SqlDbType.VarChar).Value = _Part_Of_Body_Injured;

                CmdDML.Parameters.Add("Part_Of_Body_Id_1", System.Data.SqlDbType.TinyInt ).Value = Part_Of_Body_Id_1;
                CmdDML.Parameters.Add("Part_Of_Body_Id_2", System.Data.SqlDbType.TinyInt).Value = Part_Of_Body_Id_2;
                CmdDML.Parameters.Add("Part_Of_Body_Id_3", System.Data.SqlDbType.TinyInt).Value = Part_Of_Body_Id_3;
                CmdDML.Parameters.Add("Part_Of_Body_Id_4", System.Data.SqlDbType.TinyInt).Value = Part_Of_Body_Id_4;


                CmdDML.Parameters.Add("Work_Location_Id", System.Data.SqlDbType.TinyInt).Value = _Work_Location_Id;

                if (_Rig_Id.HasValue)
                    CmdDML.Parameters.Add("Rig_Id", System.Data.SqlDbType.SmallInt).Value = _Rig_Id;
                else
                    CmdDML.Parameters.Add("Rig_Id", System.Data.SqlDbType.SmallInt).Value = DBNull.Value;

                if (!string.IsNullOrEmpty(_Unit_Name))
                    CmdDML.Parameters.Add("Unit_Name", System.Data.SqlDbType.VarChar).Value = _Unit_Name;
                else
                    CmdDML.Parameters.Add("Unit_Name", System.Data.SqlDbType.VarChar).Value = DBNull.Value;

                CmdDML.Parameters.Add("Rig_Incident_No", System.Data.SqlDbType.VarChar).Value = _Rig_Incident_No;

               // CmdDML.Parameters.Add("Incident_No", System.Data.SqlDbType.TinyInt).Value = _Incident_No;

                CmdDML.Parameters.Add("Incident_Date", System.Data.SqlDbType.DateTime).Value = Convert.ToDateTime(DateTime.ParseExact(_Incident_Date + " " + _Incident_Time + ":00", "dd/MM/yyyy HH:mm:ss", null));


                if (_Country_Id.HasValue)
                    CmdDML.Parameters.Add("Country_Id", System.Data.SqlDbType.SmallInt).Value = _Country_Id;
                else
                    CmdDML.Parameters.Add("Country_Id", System.Data.SqlDbType.SmallInt).Value = DBNull.Value;

                if (!string.IsNullOrEmpty(_Well_No))
                    CmdDML.Parameters.Add("Well_No", System.Data.SqlDbType.VarChar).Value = _Well_No;
                else
                    CmdDML.Parameters.Add("Well_No", System.Data.SqlDbType.VarChar).Value = DBNull.Value;

                if (!string.IsNullOrEmpty(_Drilling_Superintendent))
                    CmdDML.Parameters.Add("Drilling_Superintendent", System.Data.SqlDbType.VarChar).Value = _Drilling_Superintendent;
                else
                    CmdDML.Parameters.Add("Drilling_Superintendent", System.Data.SqlDbType.VarChar).Value = DBNull.Value;


                if (!string.IsNullOrEmpty(_Safety_Officer))

                    CmdDML.Parameters.Add("Safety_Officer", System.Data.SqlDbType.VarChar).Value = _Safety_Officer;
                else
                    CmdDML.Parameters.Add("Safety_Officer", System.Data.SqlDbType.VarChar).Value = DBNull.Value;



                CmdDML.Parameters.Add("Incident_Descr", System.Data.SqlDbType.VarChar).Value = _Incident_Descr;

                CmdDML.Parameters.Add("Incident_Severity", System.Data.SqlDbType.VarChar).Value = _Incident_Severity;
                CmdDML.Parameters.Add("Incident_Severity_Potential", System.Data.SqlDbType.VarChar).Value = _Incident_Severity_Potential;
                CmdDML.Parameters.Add("Incident_Type_Id", System.Data.SqlDbType.TinyInt).Value = _Incident_Type_Id;


                CmdDML.Parameters.Add("Immediate_Incident_Cause_Id", System.Data.SqlDbType.TinyInt).Value = _Immediate_Incident_Cause_Id_1;

                if (_Immediate_Incident_Cause_Id_2.HasValue)
                    CmdDML.Parameters.Add("Immediate_Incident_Cause_Id_2", System.Data.SqlDbType.TinyInt).Value = _Immediate_Incident_Cause_Id_2;
                else
                    CmdDML.Parameters.Add("Immediate_Incident_Cause_Id_2", System.Data.SqlDbType.TinyInt).Value = DBNull.Value;


                if (!string.IsNullOrEmpty(_Immediate_Cause_Descr))

                    CmdDML.Parameters.Add("Immediate_Cause_Descr", System.Data.SqlDbType.VarChar).Value = _Immediate_Cause_Descr;
                else
                    CmdDML.Parameters.Add("Immediate_Cause_Descr", System.Data.SqlDbType.VarChar).Value = DBNull.Value;

                CmdDML.Parameters.Add("Rig_Operation_Id", System.Data.SqlDbType.TinyInt).Value = _Rig_Operation_Id;
                CmdDML.Parameters.Add("Contact_Expo_Type_Id", System.Data.SqlDbType.TinyInt).Value = _Contact_Expo_Type_Id;

                if (!String.IsNullOrEmpty(_Corrective_Action))
                    CmdDML.Parameters.Add("Corrective_Action", System.Data.SqlDbType.VarChar).Value = _Corrective_Action;
                else
                    CmdDML.Parameters.Add("Corrective_Action", System.Data.SqlDbType.VarChar).Value = DBNull.Value;

                if (!String.IsNullOrEmpty(_Preventive_Action))
                    CmdDML.Parameters.Add("Preventive_Action", System.Data.SqlDbType.VarChar).Value = _Preventive_Action;
                else
                    CmdDML.Parameters.Add("Preventive_Action", System.Data.SqlDbType.VarChar).Value = DBNull.Value;


                //CmdDML.Parameters.Add("Incident_Status", System.Data.SqlDbType.VarChar).Value = _Incident_Status;


                if (_NPT_Hrs_Loss.HasValue)
                    CmdDML.Parameters.Add("NPT_Hrs_Loss", System.Data.SqlDbType.Decimal).Value = _NPT_Hrs_Loss;
                else
                    CmdDML.Parameters.Add("NPT_Hrs_Loss", System.Data.SqlDbType.Decimal).Value = DBNull.Value;

                if (_Manhours_Loss.HasValue)
                    CmdDML.Parameters.Add("Manhours_Loss", System.Data.SqlDbType.Decimal).Value = _Manhours_Loss;
                else
                    CmdDML.Parameters.Add("Manhours_Loss", System.Data.SqlDbType.Decimal).Value = DBNull.Value;

                if (_Financial_Loss_Currency_Id.HasValue)
                    CmdDML.Parameters.Add("Financial_Loss_Currency_Id", System.Data.SqlDbType.TinyInt).Value = _Financial_Loss_Currency_Id;
                else
                    CmdDML.Parameters.Add("Financial_Loss_Currency_Id", System.Data.SqlDbType.TinyInt).Value = DBNull.Value;

                if (_Financial_Loss_Amt.HasValue)
                    CmdDML.Parameters.Add("Financial_Loss_Amt", System.Data.SqlDbType.Int).Value = _Financial_Loss_Amt;
                else
                    CmdDML.Parameters.Add("Financial_Loss_Amt", System.Data.SqlDbType.Int).Value = DBNull.Value;


                if (_Exchange_Rate.HasValue)
                    CmdDML.Parameters.Add("Exchange_Rate", System.Data.SqlDbType.Decimal).Value = _Exchange_Rate;
                else
                    CmdDML.Parameters.Add("Exchange_Rate", System.Data.SqlDbType.Decimal).Value = DBNull.Value;

                if (_Financial_Loss_BC_Amt.HasValue)
                    CmdDML.Parameters.Add("Financial_Loss_BC_Amt", System.Data.SqlDbType.Int).Value = _Financial_Loss_BC_Amt;
                else
                    CmdDML.Parameters.Add("Financial_Loss_BC_Amt", System.Data.SqlDbType.Int).Value = DBNull.Value;



                if (!String.IsNullOrEmpty(_Third_Party))
                    CmdDML.Parameters.Add("Third_Party", System.Data.SqlDbType.VarChar).Value = _Third_Party;
                else
                    CmdDML.Parameters.Add("Third_Party", System.Data.SqlDbType.VarChar).Value = DBNull.Value;

                if (!String.IsNullOrEmpty(_Incident_Party))
                    CmdDML.Parameters.Add("Incident_Party", System.Data.SqlDbType.VarChar).Value = _Incident_Party;
                else
                    CmdDML.Parameters.Add("Incident_Party", System.Data.SqlDbType.VarChar).Value = DBNull.Value;

                
                if (_Contractor_Id.HasValue)
                    CmdDML.Parameters.Add("Contractor_Id", System.Data.SqlDbType.SmallInt).Value = _Contractor_Id;
                else
                    CmdDML.Parameters.Add("Contractor_Id", System.Data.SqlDbType.SmallInt).Value = DBNull.Value;

                if (_Operator_Id.HasValue)
                    CmdDML.Parameters.Add("Operator_Id", System.Data.SqlDbType.SmallInt).Value = _Operator_Id;
                else
                    CmdDML.Parameters.Add("Operator_Id", System.Data.SqlDbType.SmallInt).Value = DBNull.Value;

                CmdDML.Parameters.Add("Incident_Reported_Dt", System.Data.SqlDbType.DateTime).Value = Convert.ToDateTime(DateTime.ParseExact(_Incident_Reported_Dt + " " + _Incident_Reported_Time + ":00", "dd/MM/yyyy HH:mm:ss", null));

                CmdDML.Parameters.Add("Person_Injured", System.Data.SqlDbType.VarChar).Value = _Person_Injured;

                if (_Fs_Emp_Id.HasValue)
                    CmdDML.Parameters.Add("Fs_Emp_Id", System.Data.SqlDbType.Int).Value = _Fs_Emp_Id;
                else
                    CmdDML.Parameters.Add("Fs_Emp_Id", System.Data.SqlDbType.Int).Value = DBNull.Value;

                if (!String.IsNullOrEmpty(_Emp_Name))
                    CmdDML.Parameters.Add("Emp_Name", System.Data.SqlDbType.VarChar).Value = _Emp_Name;
                else
                    CmdDML.Parameters.Add("Emp_Name", System.Data.SqlDbType.VarChar).Value = DBNull.Value;

                if (_Rank_Id.HasValue)
                    CmdDML.Parameters.Add("Rank_Id", System.Data.SqlDbType.TinyInt).Value = _Rank_Id;
                else
                    CmdDML.Parameters.Add("Rank_Id", System.Data.SqlDbType.TinyInt).Value = DBNull.Value;

                
                if (_Total_Rig_Exp_Months.HasValue)
                    CmdDML.Parameters.Add("Total_Rig_Exp_Months", System.Data.SqlDbType.SmallInt).Value = _Total_Rig_Exp_Months;
                else
                    CmdDML.Parameters.Add("Total_Rig_Exp_Months", System.Data.SqlDbType.SmallInt).Value = DBNull.Value;

                if (!String.IsNullOrEmpty(_Comments))
                    CmdDML.Parameters.Add("Comments", System.Data.SqlDbType.VarChar).Value = _Comments;
                else
                    CmdDML.Parameters.Add("Comments", System.Data.SqlDbType.VarChar).Value = DBNull.Value;


                if (!String.IsNullOrEmpty(_Reported_By))
                    CmdDML.Parameters.Add("Reported_By", System.Data.SqlDbType.VarChar).Value = _Reported_By;

                else
                    CmdDML.Parameters.Add("Reported_By", System.Data.SqlDbType.VarChar).Value = DBNull.Value;

                if (_Rptd_By_Rank_Id.HasValue)
                    CmdDML.Parameters.Add("Rptd_By_Rank_Id", System.Data.SqlDbType.Int).Value = _Rptd_By_Rank_Id;
                else
                    CmdDML.Parameters.Add("Rptd_By_Rank_Id", System.Data.SqlDbType.Int).Value = DBNull.Value;


                CmdDML.Parameters.Add("Cr_User_Id", System.Data.SqlDbType.SmallInt).Value = Cr_User_Id;
                //sumit...
                if (!string.IsNullOrEmpty(_DMS_Path_QHSE))
                    CmdDML.Parameters.Add("DMS_Path_QHSE", System.Data.SqlDbType.VarChar).Value = _DMS_Path_QHSE;
                else
                    CmdDML.Parameters.Add("DMS_Path_QHSE", System.Data.SqlDbType.VarChar).Value = DBNull.Value;

                CmdDML.Parameters.Add("Record_Status", System.Data.SqlDbType.VarChar).Value = "Insert";
                CmdDML.ExecuteNonQuery();
                 

                /// Get Incident_Id
                if (!string.IsNullOrEmpty(CmdDML.Parameters["Incident_Id"].Value.ToString()))
                {
                    _Incident_Id = Convert.ToInt16(CmdDML.Parameters["Incident_Id"].Value.ToString());                  
                }
                else
                {
                    throw new Exception(ErrorString);
                }

                ///as we r in Add Mode so no need to check from database that any image is inserted or not 
                ///So assign  value of   isImg_Uploaded_Count == "N"
                ///and in update mode it will be checked from Db itself

                isImg_Uploaded_Count = "N";
                ErrorString = Insert_Incident_Images(ref grdInc_Images,ref Conn,ref trDML);

                if (!string.IsNullOrEmpty(ErrorString))
                {
                    throw new Exception(ErrorString);
                }
                 

              //  trDML.Commit();
            }
            catch (SqlException sqlexep)
            {
                ErrorString = "Err:" + sqlexep.Message.ToString();
            }
            catch (Exception exep)
            {

                ErrorString = "Err:" + exep.Message.ToString();
            }
            //catch (SqlException sqlexep)
            //{
            //  //  trDML.Rollback();
            //    ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            //}
            //catch (Exception exep)
            //{
            //   // trDML.Rollback();
            //    ErrorString = new  EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            //}
            finally
            {
                
            }
        }

         

        private string Insert_Incident_Images(ref GridView grdInc_Images,ref SqlConnection Conn, ref SqlTransaction trDML)
        {

            string strFileName = "",
                strPath = "~/Images/Incident_Photos/", 
                //This  variable is used to Upload the File physically in this FOLDER.
                strFile_Extention = "";
               //This variable is used to store the path in Database.(Beca)
            string strIncident_Photo_Path = "/Images/Incident_Photos/";

            int intImg_Count = 1;

            #region Insert Images

            foreach (GridViewRow grdRow in grdInc_Images.Rows)
            {
                FileUpload Image_FileUploader = (FileUpload)grdRow.FindControl("fupd_Inc_Images");

                bool blnImage_Success_Uploaded = false;

                if (Image_FileUploader.HasFile)
                {
                    #region Get the File Name and Extention.

                    if (isImg_Uploaded_Count == "N")
                    {
                        strFileName = Incident_Id.ToString() + "_" + intImg_Count.ToString();
                    }
                    else 
                    ///take the Highest Max image number of the incident from the database of that INCIDENT No.
                    {
                        string strErr = "";

                        string strImgCount = Get_Incident_Image_Max_Number(Incident_Id, ref Conn, ref trDML, out strErr);
                        
                        if (string.IsNullOrEmpty(strErr))///Error is Empty ie value is retrieved from the database.                                                         
                        {
                            strFileName = Incident_Id.ToString() + "_" + strImgCount;
                        }
                        else
                        {
                            throw (new Exception(strErr));
                        }
                    }

                    strFile_Extention = System.IO.Path.GetExtension(Image_FileUploader.FileName).ToLower();

                    //Upload the Image at mentioned Folder Path
                    blnImage_Success_Uploaded = Upload_Incident_Image(ref Image_FileUploader, strPath, strFileName, strFile_Extention);

                    #endregion

                    #region Save the Image Name and Path in database.
                    if (blnImage_Success_Uploaded == false)
                    {
                        return ErrorString ;
                    }
                    else
                    {
                        ErrorString = Store_Incident_Image_Path(_Incident_Id, strIncident_Photo_Path + strFileName + strFile_Extention, ref Conn, ref trDML);

                        if (!string.IsNullOrEmpty(ErrorString))
                        {
                            return ErrorString;
                        }
                    }

                    #endregion

                    intImg_Count = intImg_Count + 1;
                }
            }
            #endregion
            return ErrorString;
        }            
        
        ///It will Upload the Image Physically in provided Folder path.         
        protected bool Upload_Incident_Image(ref FileUpload Image_FileUploader, string strPath, string strFileName,string strFile_Extention)//ref FileUpload FileUploader,
        {
            
            Boolean fileOK = false;

            String path = HttpContext.Current.Server.MapPath(strPath); 
            if (Image_FileUploader.HasFile)
            {
                String fileExtension = System.IO.Path.GetExtension(Image_FileUploader.FileName).ToLower();
                String[] allowedExtensions = { ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".png" };

                for (int i = 0; i < allowedExtensions.Length; i++)
                {
                    if (fileExtension == allowedExtensions[i])
                    {
                        fileOK = true;
                    }
                }
            }

            if (fileOK)
            {
                try
                {

                    Image_FileUploader.PostedFile.SaveAs(path + strFileName + strFile_Extention);
                }
                catch (Exception ex)
                {
                    ErrorString = "File could not be Uploaded!!![" + ex.Message.ToString() + "]";
                    return false;
                }
            }
            else
            {
                ErrorString = "Invalid File Type!!!";
                return false;
            }

 
            return true;
        }
        
        ///It will Store the Image path in Database.   
        private string Store_Incident_Image_Path(int intPrmKey_Value, string strIncident_Photo_Path, ref SqlConnection Conn, ref SqlTransaction trDML)
        {
            try
            {
                SqlCommand CmdDML = new SqlCommand(OI.Def +"Prc_Incident_Photos", Conn, trDML);
                CmdDML.CommandType = CommandType.StoredProcedure;


                CmdDML.Parameters.Add("Incident_Id", System.Data.SqlDbType.Int).Value = intPrmKey_Value;
                CmdDML.Parameters.Add("Incident_Photo_Path", System.Data.SqlDbType.VarChar).Value = strIncident_Photo_Path;
                CmdDML.Parameters.Add("Record_Status", System.Data.SqlDbType.VarChar).Value = "Insert";
                CmdDML.ExecuteNonQuery();
            }
            catch (SqlException Sqlexep)
            {
                ErrorString = Sqlexep.Message;

            }
            catch (Exception exep)
            {
                ErrorString = exep.Message;

            }
            return ErrorString;
        }
        
        ///It will Store the Image path in Database.   
        private string Get_Incident_Image_Max_Number(int intPrmKey_Value, ref SqlConnection Conn, ref SqlTransaction trDML, out string errorString)
        {
            string strResult = ""; errorString = "";
            try
            {
                SqlCommand CmdDML = new SqlCommand(OI.Def + "Prc_Incident_Photos", Conn, trDML);
                CmdDML.CommandType = CommandType.StoredProcedure;


                CmdDML.Parameters.Add("Incident_Id", System.Data.SqlDbType.Int).Value = intPrmKey_Value;
                
                CmdDML.Parameters.Add("Record_Status", System.Data.SqlDbType.VarChar).Value = "Ret_Incident_Image_Max_Number";
                strResult = CmdDML.ExecuteScalar().ToString();
                
            }
            catch (SqlException Sqlexep)
            {
                errorString = Sqlexep.Message;
                return errorString; 
            }
            catch (Exception exep)
            {
                errorString = exep.Message;
                return errorString;
            }
            return strResult;
        }

        ///It will Return Y/N Indication that Images are uploaded or not
        private string Check_Images_Uploaded(int intPrmKey_Value, ref SqlConnection Conn, ref SqlTransaction trDML, out string errorString)
        {
            string strResult = ""; errorString = "";
            try
            {
                SqlCommand CmdDML = new SqlCommand(OI.Def + "Prc_Incident_Photos", Conn, trDML);
                CmdDML.CommandType = CommandType.StoredProcedure;
                CmdDML.Parameters.Add("Incident_Id", System.Data.SqlDbType.Int).Value = intPrmKey_Value;
                CmdDML.Parameters.Add("Record_Status", System.Data.SqlDbType.VarChar).Value = "Is_Images_Uploaded";
                strResult = CmdDML.ExecuteScalar().ToString();
                
            }
            catch (SqlException Sqlexep)
            {
                errorString = Sqlexep.Message;
                return errorString; 
            }
            catch (Exception exep)
            {
                errorString = exep.Message;
                return errorString;
            }
            return strResult;
        }

        
        ///It will Delete the Image path from the Databse and Also delete it physically from the Folder.   
        public string Delete_Incident_Image(int intPrmKey_Value, string strFileName, ref SqlConnection Conn, ref SqlTransaction trDML)
        {
            try
            {

                #region  Delete the Record from the Table
                SqlCommand CmdDML = new SqlCommand(OI.Def + "Prc_Incident_Photos", Conn, trDML);
                CmdDML.CommandType = CommandType.StoredProcedure;

                CmdDML.Parameters.Add("Incident_Photo_Id", System.Data.SqlDbType.Int).Value = intPrmKey_Value;
                CmdDML.Parameters.Add("Record_Status", System.Data.SqlDbType.VarChar).Value = "Delete_Incident_Img";

                CmdDML.ExecuteNonQuery();
                #endregion


                #region Delete the FILE from the Location
                if (System.IO.File.Exists(HttpContext.Current.Server.MapPath(strFileName)))
                {
                    System.IO.File.Delete(HttpContext.Current.Server.MapPath(strFileName));
                }
                #endregion

            }
            catch (SqlException Sqlexep)
            {
                ErrorString = Sqlexep.Message;

            }
            catch (Exception exep)
            {
                ErrorString = exep.Message;

            }
            return ErrorString;
        }

        public void DeleteMe(DataTable DtIncident_Img_Path)
        {

            SqlTransaction trDML;
            SqlCommand CmdDML;

            Conn.Open();
            trDML = Conn.BeginTransaction();
            try
            {
                // aspe rchanges on 17 feb no physical delete
                //if (DtIncident_Img_Path != null)
                //{
                //    for (int intRow = 0; intRow < DtIncident_Img_Path.Rows.Count; intRow++)
                //    {
                //        string tbIncident_Photo_Path = DtIncident_Img_Path.Rows[intRow]["Incident_Photo_Path"].ToString().Trim();
                //        string tbIncident_Photo_Id = DtIncident_Img_Path.Rows[intRow]["Incident_Photo_Id"].ToString().Trim();

                //        int intIncident_Photo_Id = Convert.ToInt32(tbIncident_Photo_Id);

                //        string strFileName = "~" + tbIncident_Photo_Path;

                //        #region Delete the File from the location
                //        ErrorString = Delete_Incident_Image(intIncident_Photo_Id, strFileName, ref Conn, ref trDML);
                //        #endregion

                //        if (!string.IsNullOrEmpty(ErrorString))
                //        {
                //            throw (new Exception(ErrorString));
                //        }

                //    }
                //}


                CmdDML = new SqlCommand(OI.Def + "Prc_Incident_Details", Conn, trDML);
                CmdDML.CommandType = CommandType.StoredProcedure;

                /*  
                 * Cascade_Delete = data deleted from 3 tables 1)eos.Incident_Photos
                 * 2)eos.Incident_Actions 3)eos.Incident_Root_Cause  
                 */
                CmdDML.Parameters.Add("Incident_Id", System.Data.SqlDbType.Int).Value = _Incident_Id;

                if (!string.IsNullOrEmpty(_Deleted_Remarks))
                    CmdDML.Parameters.Add("Deleted_Remarks", System.Data.SqlDbType.VarChar).Value = _Deleted_Remarks;
                else
                    CmdDML.Parameters.Add("Deleted_Remarks", System.Data.SqlDbType.VarChar).Value = DBNull.Value;
     
                CmdDML.Parameters.Add("Record_Status", System.Data.SqlDbType.VarChar).Value = "Cascade_Delete";
                CmdDML.ExecuteNonQuery();

                
                trDML.Commit();
            }
            catch (SqlException sqlexep)
            {
                trDML.Rollback();
                ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            }
            catch (Exception exep)
            {
                trDML.Rollback();
                ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            }
            finally
            {
                if (Conn.State == ConnectionState.Open)
                {
                    Conn.Close();
                    Conn.Dispose();
                }
            }

        }

        public void UpdateMe(ref GridView grdUploaded_Images, ref GridView grdInc_Images)
        {


            SqlTransaction trDML;
            SqlCommand CmdDML;             
            Conn.Open();
            trDML = Conn.BeginTransaction();
            try
            {
                #region Update the Incident
                CmdDML = new SqlCommand(OI.Def + "Prc_Incident_Details", Conn, trDML);
                CmdDML.CommandType = CommandType.StoredProcedure;

                //Changes By Vipin Add Part_Of_Body_Injured
                //CmdDML.Parameters.Add("Part_Of_Body_Injured", System.Data.SqlDbType.VarChar).Value = _Part_Of_Body_Injured;

                CmdDML.Parameters.Add("Rig_Incident_No", System.Data.SqlDbType.VarChar).Value = _Rig_Incident_No;
                CmdDML.Parameters.Add("Part_Of_Body_Id_1", System.Data.SqlDbType.TinyInt).Value = Part_Of_Body_Id_1;
                CmdDML.Parameters.Add("Part_Of_Body_Id_2", System.Data.SqlDbType.TinyInt).Value = Part_Of_Body_Id_2;
                CmdDML.Parameters.Add("Part_Of_Body_Id_3", System.Data.SqlDbType.TinyInt).Value = Part_Of_Body_Id_3;
                CmdDML.Parameters.Add("Part_Of_Body_Id_4", System.Data.SqlDbType.TinyInt).Value = Part_Of_Body_Id_4;
                
                CmdDML.Parameters.Add("Incident_Id", System.Data.SqlDbType.Int).Value = _Incident_Id;


                CmdDML.Parameters.Add("Person_Injured", System.Data.SqlDbType.VarChar).Value = _Person_Injured;

                if (!String.IsNullOrEmpty(_Third_Party))
                    CmdDML.Parameters.Add("Third_Party", System.Data.SqlDbType.VarChar).Value = _Third_Party;
                else
                    CmdDML.Parameters.Add("Third_Party", System.Data.SqlDbType.VarChar).Value = DBNull.Value;

                if (!String.IsNullOrEmpty(_Incident_Party))
                    CmdDML.Parameters.Add("Incident_Party", System.Data.SqlDbType.VarChar).Value = _Incident_Party;
                else
                    CmdDML.Parameters.Add("Incident_Party", System.Data.SqlDbType.VarChar).Value = DBNull.Value;

                if (_Contractor_Id.HasValue)
                    CmdDML.Parameters.Add("Contractor_Id", System.Data.SqlDbType.SmallInt).Value = _Contractor_Id;
                else
                    CmdDML.Parameters.Add("Contractor_Id", System.Data.SqlDbType.SmallInt).Value = DBNull.Value;



                if (!String.IsNullOrEmpty(_Emp_Name))
                    CmdDML.Parameters.Add("Emp_Name", System.Data.SqlDbType.VarChar).Value = _Emp_Name;
                else
                    CmdDML.Parameters.Add("Emp_Name", System.Data.SqlDbType.VarChar).Value = DBNull.Value;


                if (_Rank_Id.HasValue)
                    CmdDML.Parameters.Add("Rank_Id", System.Data.SqlDbType.TinyInt).Value = _Rank_Id;
                else
                    CmdDML.Parameters.Add("Rank_Id", System.Data.SqlDbType.TinyInt).Value = DBNull.Value;


                if (_Total_Rig_Exp_Months.HasValue)
                    CmdDML.Parameters.Add("Total_Rig_Exp_Months", System.Data.SqlDbType.SmallInt).Value = _Total_Rig_Exp_Months;
                else
                    CmdDML.Parameters.Add("Total_Rig_Exp_Months", System.Data.SqlDbType.SmallInt).Value = DBNull.Value;


                CmdDML.Parameters.Add("Incident_Descr", System.Data.SqlDbType.VarChar).Value = _Incident_Descr;

                if (!string.IsNullOrEmpty(_Immediate_Cause_Descr))

                    CmdDML.Parameters.Add("Immediate_Cause_Descr", System.Data.SqlDbType.VarChar).Value = _Immediate_Cause_Descr;
                else
                    CmdDML.Parameters.Add("Immediate_Cause_Descr", System.Data.SqlDbType.VarChar).Value = DBNull.Value;

                if (String.IsNullOrEmpty(_Corrective_Action))
                    CmdDML.Parameters.Add("Corrective_Action", System.Data.SqlDbType.VarChar).Value = DBNull.Value;
                else
                    CmdDML.Parameters.Add("Corrective_Action", System.Data.SqlDbType.VarChar).Value = _Corrective_Action;

                if (String.IsNullOrEmpty(_Preventive_Action))
                    CmdDML.Parameters.Add("Preventive_Action", System.Data.SqlDbType.VarChar).Value = DBNull.Value;
                else
                    CmdDML.Parameters.Add("Preventive_Action", System.Data.SqlDbType.VarChar).Value = _Preventive_Action;
                
                if (!String.IsNullOrEmpty(_Comments))
                    CmdDML.Parameters.Add("Comments", System.Data.SqlDbType.VarChar).Value = _Comments;
                else
                    CmdDML.Parameters.Add("Comments", System.Data.SqlDbType.VarChar).Value = DBNull.Value;

                if (_NPT_Hrs_Loss.HasValue)
                    CmdDML.Parameters.Add("NPT_Hrs_Loss", System.Data.SqlDbType.Decimal).Value = _NPT_Hrs_Loss;
                else
                    CmdDML.Parameters.Add("NPT_Hrs_Loss", System.Data.SqlDbType.Decimal).Value = DBNull.Value;


                if (_Manhours_Loss.HasValue)
                    CmdDML.Parameters.Add("Manhours_Loss", System.Data.SqlDbType.Decimal).Value = _Manhours_Loss;
                else
                    CmdDML.Parameters.Add("Manhours_Loss", System.Data.SqlDbType.Decimal).Value = DBNull.Value;

                if (_Financial_Loss_Currency_Id.HasValue)
                    CmdDML.Parameters.Add("Financial_Loss_Currency_Id", System.Data.SqlDbType.TinyInt).Value = _Financial_Loss_Currency_Id;
                else
                    CmdDML.Parameters.Add("Financial_Loss_Currency_Id", System.Data.SqlDbType.TinyInt).Value = DBNull.Value;

                if (_Financial_Loss_Amt.HasValue)
                    CmdDML.Parameters.Add("Financial_Loss_Amt", System.Data.SqlDbType.Int).Value = _Financial_Loss_Amt;
                else
                    CmdDML.Parameters.Add("Financial_Loss_Amt", System.Data.SqlDbType.Int).Value = DBNull.Value;


                if (_Exchange_Rate.HasValue)
                    CmdDML.Parameters.Add("Exchange_Rate", System.Data.SqlDbType.Decimal).Value = _Exchange_Rate;
                else
                    CmdDML.Parameters.Add("Exchange_Rate", System.Data.SqlDbType.Decimal).Value = DBNull.Value;

                if (_Financial_Loss_BC_Amt.HasValue)
                    CmdDML.Parameters.Add("Financial_Loss_BC_Amt", System.Data.SqlDbType.Int).Value = _Financial_Loss_BC_Amt;
                else
                    CmdDML.Parameters.Add("Financial_Loss_BC_Amt", System.Data.SqlDbType.Int).Value = DBNull.Value;


                if (!String.IsNullOrEmpty(_Reported_By))
                    CmdDML.Parameters.Add("Reported_By", System.Data.SqlDbType.VarChar).Value = _Reported_By;

                else
                    CmdDML.Parameters.Add("Reported_By", System.Data.SqlDbType.VarChar).Value = DBNull.Value;

                if (_Rptd_By_Rank_Id.HasValue)
                    CmdDML.Parameters.Add("Rptd_By_Rank_Id", System.Data.SqlDbType.Int).Value = _Rptd_By_Rank_Id;
                else
                    CmdDML.Parameters.Add("Rptd_By_Rank_Id", System.Data.SqlDbType.Int).Value = DBNull.Value;


                //CmdDML.Parameters.Add("Incident_Status", System.Data.SqlDbType.VarChar).Value = _Incident_Status;
                CmdDML.Parameters.Add("Mod_User_Id", System.Data.SqlDbType.SmallInt).Value = Mod_User_Id;
                CmdDML.Parameters.Add("Record_Status", System.Data.SqlDbType.VarChar).Value = "Update";

                if (!string.IsNullOrEmpty(_DMS_Path_QHSE))
                    CmdDML.Parameters.Add("DMS_Path_QHSE", System.Data.SqlDbType.VarChar).Value = _DMS_Path_QHSE;
                else
                    CmdDML.Parameters.Add("DMS_Path_QHSE", System.Data.SqlDbType.VarChar).Value = DBNull.Value;

                if (!string.IsNullOrEmpty(_Well_No))
                    CmdDML.Parameters.Add("Well_No", System.Data.SqlDbType.VarChar).Value = _Well_No;
                else
                    CmdDML.Parameters.Add("Well_No", System.Data.SqlDbType.VarChar).Value = DBNull.Value;


                if (_Operator_Id.HasValue)
                    CmdDML.Parameters.Add("Operator_Id", System.Data.SqlDbType.SmallInt).Value = _Operator_Id;
                else
                    CmdDML.Parameters.Add("Operator_Id", System.Data.SqlDbType.SmallInt).Value = DBNull.Value;

                CmdDML.Parameters.Add("Incident_Severity", System.Data.SqlDbType.VarChar).Value = _Incident_Severity;
                CmdDML.Parameters.Add("Incident_Severity_Potential", System.Data.SqlDbType.VarChar).Value = _Incident_Severity_Potential;
            

                CmdDML.ExecuteNonQuery();
                #endregion

                #region Delete the Selected Images from the Grid
                foreach (GridViewRow grdRow in grdUploaded_Images.Rows)
                {
                    HtmlInputCheckBox chkSelect = (HtmlInputCheckBox)grdRow.FindControl("chkSelect");
                    if (chkSelect.Checked)
                    {
                        HtmlInputHidden tbIncident_Photo_Path = (HtmlInputHidden)grdRow.FindControl("tbIncident_Photo_Path_Hidden");
                        HtmlInputHidden tbIncident_Photo_Id = (HtmlInputHidden)grdRow.FindControl("tbIncident_Photo_Id_Hidden");

                        int intIncident_Photo_Id = Convert.ToInt32(tbIncident_Photo_Id.Value);

                        string strFileName = "~" + tbIncident_Photo_Path.Value;              

                        #region Delete the File from the location
                        ErrorString = Delete_Incident_Image(intIncident_Photo_Id, strFileName, ref Conn, ref trDML);
                        #endregion

                        if (!string.IsNullOrEmpty(ErrorString))
                        {
                            throw (new Exception(ErrorString));
                        }
                        
                    }
                }
                 #endregion


                #region  Get the Count of the images uploaded for that Incident
                string strImgErr = "";
                isImg_Uploaded_Count = Check_Images_Uploaded(Incident_Id , ref Conn, ref trDML, out strImgErr);

                if (!string.IsNullOrEmpty(strImgErr))///Error is Empty ie value is retrieved from the database.                                                         
                {
                    throw (new Exception(strImgErr));
                }

                #endregion


                #region  Add the new images for the Existing Incident.
                ErrorString = Insert_Incident_Images(ref grdInc_Images, ref Conn, ref trDML);             


                if (!string.IsNullOrEmpty(ErrorString))///Error is Empty ie value is retrieved from the database.                                                         
                {
                    throw (new Exception(ErrorString));
                }
                #endregion

                trDML.Commit();
            }
            catch (SqlException sqlexep)
            {
                trDML.Rollback();
                ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            }
            catch (Exception exep)
            {
                trDML.Rollback();
                ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            }
            finally
            {
                if (Conn.State == ConnectionState.Open)
                {
                    Conn.Close();
                    Conn.Dispose();
                }
            }
        }

       
    }
}
